"""Pytest configuration — shared fixtures for all tests."""

import threading
import uuid
from collections.abc import Generator

import can
import pytest
from can import Message

from pyccp.master import Master

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


CRO = 0x7E1
DTO = 0x815


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
        self._lock = threading.Lock()
        self.received: list[Message] = []

    @property
    def reply(self):
        with self._lock:
            return self.reply_fn

    @reply.setter
    def reply(self, fn):
        with self._lock:
            self.reply_fn = fn

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

            reply_fn = self.reply

            if reply_fn:
                code, tail = reply_fn(ctr, cmd, payload)
            else:
                code, tail = 0x00, b""

            reply = make_crm(ctr, code, tail, self.dto)
            self.bus.send(reply)

    def stop(self):
        if self.bus is not None:
            self._stop.set()
            self.join()
            self.bus.shutdown()
            self.bus = None


@pytest.fixture
def _channel():
    """Return a unique channel name so tests do not interfere with each other."""
    return f"ccp-test-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def slave(_channel) -> Generator[SlaveResponder, None, None]:
    """Create a SlaveResponder on a fresh virtual channel with default ACK replies.

    The slave's `channel` attribute holds the channel name for the master to use.
    """
    ch = _channel
    slave_bus = can.interface.Bus(ch, interface="virtual")
    responder = SlaveResponder(slave_bus, CRO, DTO, None)
    responder.start()
    yield responder
    responder.stop()


@pytest.fixture
def master(_channel) -> Generator[Master, None, None]:
    """Create a Master connected to the same virtual channel as the slave.

    Uses the proper context manager pattern: `with Master(...) as master`.
    """
    ch = _channel
    master_bus = can.interface.Bus(ch, interface="virtual")

    with Master(master_bus, CRO, DTO) as m:
        yield m
