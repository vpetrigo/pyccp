"""DAQ Sender tests — verify Client DAQ sender functionality with event channels.

Tests that enabled DAQs allow normal DTO response sending when CRO arrives,
covering all 9 event channels with their corresponding rasters:

 * Event Channel #0 -> 1 ms raster
 * Event Channel #1 -> 2 ms raster
 * Event Channel #2 -> 5 ms raster
 * Event Channel #3 -> 10 ms raster
 * Event Channel #4 -> 20 ms raster
 * Event Channel #5 -> 50 ms raster
 * Event Channel #6 -> 100 ms raster
 * Event Channel #7 -> 200 ms raster
 * Event Channel #8 -> 500 ms raster
"""

import time
from typing import Optional

import can
from can import Message

from pyccp.ccp import DAQMessage, ReturnCodes

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CRO = 0x7E1
_DTO = 0x815
_DAQ_ID = 0x1A0  # DAQ list arbitration ID
_STATION = 0x1234

# Event channel rasters per CCP 2.1 specification
EVENT_CHANNEL_RASTERS = {
    0: 1,  # 1 ms raster
    1: 2,  # 2 ms raster
    2: 5,  # 5 ms raster
    3: 10,  # 10 ms raster
    4: 20,  # 20 ms raster
    5: 50,  # 50 ms raster
    6: 100,  # 100 ms raster
    7: 200,  # 200 ms raster
    8: 500,  # 500 ms raster
}


def _recv_by_id(
    bus: can.BusABC, target_id: int, timeout: float = 2.0
) -> Optional[Message]:
    """Receive a message with a specific arbitration ID, skipping other traffic."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        residual = deadline - time.monotonic()
        msg = bus.recv(timeout=min(residual, 0.1))
        if msg is None:
            return None
        if msg.arbitration_id == target_id:
            return msg
    return None


class TestDAQSender:
    """Tests for Client._DAQSender functionality using the slave/master fixtures."""

    def test_daq_sender_sends_daq_message(self, slave, master, _channel):
        """Verify _DAQSender can queue and send a DAQ message through the bus."""
        observer_bus = can.interface.Bus(_channel, interface="virtual")

        # Send a DAQ message via the slave's DAQ sender
        daq_msg = DAQMessage(
            Message(arbitration_id=_DAQ_ID, data=b"\x10\x01\x02\x03\x00\x00\x00\x00")
        )
        slave._daq_sender.send_daq(daq_msg)

        # The observer should receive the DAQ message
        msg = _recv_by_id(observer_bus, _DAQ_ID)
        assert msg is not None
        assert msg.data[0] == 0x10  # PID
        assert msg.data[1:4] == b"\x01\x02\x03"
        observer_bus.shutdown()

    def test_daq_sender_sends_multiple_messages(self, slave, master, _channel):
        """Verify _DAQSender can queue and send multiple DAQ messages in order."""
        observer_bus = can.interface.Bus(_channel, interface="virtual")

        # Queue several DAQ messages
        for i in range(5):
            daq_msg = DAQMessage(
                Message(
                    arbitration_id=_DAQ_ID,
                    data=bytes([0x10 + i, i, i + 1, i + 2, 0, 0, 0, 0]),
                )
            )
            slave._daq_sender.send_daq(daq_msg)

        # Receive all messages
        received = []
        for _ in range(5):
            msg = _recv_by_id(observer_bus, _DAQ_ID)
            if msg is None:
                break
            received.append(msg)

        assert len(received) == 5
        for i, msg in enumerate(received):
            assert msg.data[0] == 0x10 + i
        observer_bus.shutdown()

    def test_daq_sender_different_daq_ids(self, slave, master, _channel):
        """Verify _DAQSender can send messages with different DAQ list IDs."""
        observer_bus = can.interface.Bus(_channel, interface="virtual")

        daq_ids = [0x1A0, 0x1A1, 0x1A2]

        for daq_id in daq_ids:
            daq_msg = DAQMessage(
                Message(arbitration_id=daq_id, data=b"\x10\xaa\xbb\x00\x00\x00\x00\x00")
            )
            slave._daq_sender.send_daq(daq_msg)

        received_ids = set()
        for daq_id in daq_ids:
            msg = _recv_by_id(observer_bus, daq_id)
            if msg is not None:
                received_ids.add(daq_id)

        assert received_ids == set(daq_ids)
        observer_bus.shutdown()


class TestDTOwithDAQEnabled:
    """Tests that DTO responses work correctly when DAQ sender is enabled.

    When DAQs are enabled (DAQ sender is running), the Client must still
    allow normal DTO response sending when a CRO arrives.
    """

    def test_dto_response_when_daq_enabled(self, slave, master):
        """Verify DTO is sent when CRO arrives while DAQ sender is active."""
        # The slave already has default ACK handlers registered.
        # Send a CONNECT command via the master — the slave should reply with DTO.
        resp = master.connect(_STATION)
        assert resp is not None
        assert resp.code == ReturnCodes.ACKNOWLEDGE

    def test_dto_and_daq_coexist(self, slave, master, _channel):
        """Verify both DTO responses and DAQ messages can be sent concurrently."""
        observer_bus = can.interface.Bus(_channel, interface="virtual")

        # 1. Send a DAQ message via the slave's DAQ sender
        daq_msg = DAQMessage(
            Message(arbitration_id=_DAQ_ID, data=b"\x10\x01\x02\x03\x00\x00\x00\x00")
        )
        slave._daq_sender.send_daq(daq_msg)

        # 2. Send a CRO via the master to trigger DTO response
        resp = master.connect(_STATION)
        assert resp is not None
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        # 3. Verify the DAQ message was also received
        daq_msg_recv = _recv_by_id(observer_bus, _DAQ_ID)
        assert daq_msg_recv is not None, "DAQ message not received"
        assert daq_msg_recv.data[0] == 0x10
        observer_bus.shutdown()

    def test_dto_response_with_daq_running_per_event_channel(self, slave, master):
        """Verify DTO response works for each event channel configuration.

        Simulates the START_STOP command for each event channel (0-8) and
        confirms that DTO responses are still delivered when CRO arrives.
        """
        for event_channel, raster in EVENT_CHANNEL_RASTERS.items():
            # Send START_STOP with the event channel and rate prescaler
            resp = master.start_stop(1, 0, 0, event_channel, raster)
            assert resp is not None, (
                f"No DTO received for event channel {event_channel}"
            )
            assert resp.code == ReturnCodes.ACKNOWLEDGE, (
                f"DTO failed for event channel {event_channel}"
            )


class TestDAQSenderEventChannels:
    """Tests DAQ sender behavior with all 9 event channel rasters."""

    def test_daq_message_per_event_channel(self, slave, master, _channel):
        """Send DAQ messages simulating each event channel's raster timing."""
        observer_bus = can.interface.Bus(_channel, interface="virtual")

        for event_channel, raster in EVENT_CHANNEL_RASTERS.items():
            daq_id = _DAQ_ID + event_channel
            pid = 0x10 + event_channel
            daq_msg = DAQMessage(
                Message(
                    arbitration_id=daq_id,
                    data=bytes([pid, event_channel, raster & 0xFF, 0, 0, 0, 0, 0]),
                )
            )
            slave._daq_sender.send_daq(daq_msg)

            msg = _recv_by_id(observer_bus, daq_id)
            assert msg is not None, (
                f"DAQ not received for event channel {event_channel}"
            )
            assert msg.data[0] == pid
            assert msg.data[1] == event_channel

        observer_bus.shutdown()

    def test_daq_sender_with_start_stop_command(self, slave, master, _channel):
        """Verify DAQ messages are sent after START_STOP enables DAQ list.

        Simulates the full flow: START_STOP command arrives, DTO is sent back,
        then DAQ messages are periodically sent on the configured event channel.
        """
        observer_bus = can.interface.Bus(_channel, interface="virtual")

        event_channel = 3  # 10 ms raster
        raster = EVENT_CHANNEL_RASTERS[event_channel]

        # Send START_STOP via master — verify DTO response
        resp = master.start_stop(1, 0, 0, event_channel, raster)
        assert resp is not None
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        # Now send DAQ messages (simulating periodic DAQ output)
        for i in range(3):
            daq_msg = DAQMessage(
                Message(arbitration_id=_DAQ_ID, data=bytes([0x10, i, 0, 0, 0, 0, 0, 0]))
            )
            slave._daq_sender.send_daq(daq_msg)

        # Verify all DAQ messages are received
        received = []
        for _ in range(3):
            msg = _recv_by_id(observer_bus, _DAQ_ID)
            if msg is None:
                break
            received.append(msg)

        assert len(received) == 3
        for i, msg in enumerate(received):
            assert msg.data[1] == i
        observer_bus.shutdown()

    def test_all_event_channels_daq_and_dto(self, slave, master, _channel):
        """Comprehensive test: for each event channel, verify both DAQ sending
        and DTO response work together.
        """
        observer_bus = can.interface.Bus(_channel, interface="virtual")

        for event_channel, raster in EVENT_CHANNEL_RASTERS.items():
            # Send DAQ message first
            daq_msg = DAQMessage(
                Message(
                    arbitration_id=_DAQ_ID,
                    data=bytes([0xFE, event_channel, raster & 0xFF, 0, 0, 0, 0, 0]),
                )
            )
            slave._daq_sender.send_daq(daq_msg)

            # Then send START_STOP CRO via master to trigger DTO
            resp = master.start_stop(1, 0, 0, event_channel, raster)
            assert resp is not None, (
                f"DTO message missing for event channel {event_channel}"
            )
            assert resp.code == ReturnCodes.ACKNOWLEDGE

            # Verify DAQ message was also received
            daq_msg_recv = _recv_by_id(observer_bus, _DAQ_ID)
            assert daq_msg_recv is not None, (
                f"DAQ message missing for event channel {event_channel}"
            )

        observer_bus.shutdown()
