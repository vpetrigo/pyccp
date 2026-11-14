"""Pytest configuration — shared fixtures for all tests."""

import threading
import uuid
from collections.abc import Callable, Generator
from typing import Optional

import can
import pytest
from can import Message

from pyccp.ccp import CRO, DTO, ReturnCodes
from pyccp.client import Client
from pyccp.master import Master

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_CRO = 0x7E1
_DTO = 0x815


def make_crm(
    ctr: int, code: int = 0x00, tail: bytes = b"", can_id: int = _DTO
) -> Message:
    """Build a Command Return Message."""
    dto = DTO.dto(ctr, ReturnCodes(code), tail)
    return Message(arbitration_id=can_id, data=dto.bytes())


class SlaveResponder(Client):
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
        station_id: int = 0x1234,
        reply_fn=None,
    ):
        super().__init__(bus, cro, dto, station_id)
        self.bus = bus
        self.cro = cro
        self.dto = dto
        self.reply_fn = reply_fn
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self.received: list[Message] = []

        for cmd in self._handlers:
            self.register_handler(
                cmd, lambda _cro: DTO.dto(_cro.ctr, ReturnCodes.ACKNOWLEDGE, b"")
            )

    def _on_message(self, message: can.Message) -> None:
        """Track received messages and delegate to parent handler."""
        self.received.append(message)
        super()._on_message(message)

    def stop(self) -> None:
        """Stop the internal receiver and sender threads."""
        if self._receiver is not None:
            self._receiver.stop()
            self._receiver = None
        if self._dto_sender is not None:
            self._dto_sender.stop()
            self._dto_sender = None
        if self._daq_sender is not None:
            self._daq_sender.stop()
            self._daq_sender = None

    @property
    def reply(self) -> Optional[Callable[[int, int, bytes], tuple[int, bytes]]]:
        with self._lock:
            return self.reply_fn

    @reply.setter
    def reply(self, fn: Callable[[int, int, bytes], tuple[int, bytes]]):
        with self._lock:
            self.reply_fn = fn

            def h(cro: CRO) -> DTO:
                code, tail = self.reply_fn(cro.ctr, cro.code, cro.data)
                return DTO.dto(cro.ctr, ReturnCodes(code), tail)

            for cmd in self._handlers:
                self.register_handler(cmd, h)


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
    with SlaveResponder(slave_bus, _CRO, _DTO) as c:
        yield c


@pytest.fixture
def master(_channel) -> Generator[Master, None, None]:
    """Create a Master connected to the same virtual channel as the slave.

    Uses the proper context manager pattern: `with Master(...) as master`.
    """
    ch = _channel
    master_bus = can.interface.Bus(ch, interface="virtual")

    with Master(master_bus, _CRO, _DTO) as m:
        yield m
