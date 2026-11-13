"""Shared helpers for Master tests using python-can virtual interface.

The virtual interface lets two Bus instances on the same channel exchange
messages, so a background *slave* thread can reply with realistic CRM frames
instead of queuing pre-baked responses on a FakeBus.
"""

import threading
import uuid

import can
from can import Message

from pyccp import ccp
from pyccp.master import Master

CRO = 0x7E1
DTO = 0x815
STATION = 0x1234


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _channel():
    """Return a unique channel name so tests do not interfere with each other."""
    return f"ccp-test-{uuid.uuid4().hex[:8]}"


def make_crm(
    ctr: int, code: int = 0x00, tail: bytes = b"", can_id: int = DTO
) -> Message:
    """Build a Command Return Message."""
    data = bytes([0xFF, code, ctr]) + bytes(tail)
    data = data.ljust(8, b"\x00")
    return Message(arbitration_id=can_id, data=data)


class SlaveResponder(threading.Thread):
    """Background thread that reads CRO frames and replies with CRMs.

    *reply_fn* is called with ``(ctr, cmd_code, payload)`` and must return
    ``(code, tail)`` where *code* is a ReturnCodes value and *tail* is the
    optional data payload (bytes).  If *reply_fn* is ``None`` the slave
    always replies ACK with no tail.
    """

    def __init__(
        self,
        bus: can.BusABC,
        cro: int,
        dto: int,
        reply_fn=None,
    ):
        super().__init__(daemon=True)
        self.bus = bus
        self.cro = cro
        self.dto = dto
        self.reply_fn = reply_fn
        self._stop = threading.Event()
        self.received: list[Message] = []

    def run(self):
        while not self._stop.is_set():
            msg = self.bus.recv(timeout=0.05)
            if msg is None:
                continue
            if msg.arbitration_id != self.cro:
                continue
            self.received.append(msg)
            ctr = msg.data[1]
            cmd = msg.data[0]
            payload = bytes(msg.data[2:])
            if self.reply_fn is not None:
                code, tail = self.reply_fn(ctr, cmd, payload)
            else:
                code, tail = 0x00, b""
            reply = make_crm(ctr, code, tail, self.dto)
            self.bus.send(reply)

    def stop(self):
        self._stop.set()
        self.join(timeout=2)


def make_master_and_slave(reply_fn=None):
    """Return ``(master, slave_thread)`` on a fresh virtual channel.

    The Master is entered via its context manager so that the internal
    _Receiver thread is started and CRM responses are dispatched to
    pending Futures.
    """
    ch = _channel()
    master_bus = can.interface.Bus(ch, interface="virtual")
    slave_bus = can.interface.Bus(ch, interface="virtual")
    master = Master(master_bus, CRO, DTO)
    master.__enter__()
    slave = SlaveResponder(slave_bus, CRO, DTO, reply_fn)
    slave.start()
    return master, slave
