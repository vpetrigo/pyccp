# -*- coding: utf-8 -*-

import logging
import queue
import time
from collections.abc import Callable
from queue import Queue
from threading import Event, Lock, Thread
from types import TracebackType
from typing import Optional

import can

from .ccp import (
    ACTION_SERVICE,
    BUILD_CHKSUM,
    CLEAR_MEMORY,
    CONNECT,
    CRO,
    DIAG_SERVICE,
    DISCONNECT,
    DNLOAD,
    DNLOAD_6,
    DTO,
    EXCHANGE_ID,
    GET_ACTIVE_CAL_PAGE,
    GET_CCP_VERSION,
    GET_DAQ_SIZE,
    GET_S_STATUS,
    # Optional Commands
    GET_SEED,
    MOVE,
    PROGRAM,
    PROGRAM_6,
    SELECT_CAL_PAGE,
    SET_DAQ_PTR,
    SET_MTA,
    SET_S_STATUS,
    SHORT_UP,
    START_STOP,
    START_STOP_ALL,
    TEST,
    UNLOCK,
    UPLOAD,
    WRITE_DAQ,
    DAQMessage,
)

_SUPPORTED_COMMAND = (
    # Mandatory Commands
    CONNECT,
    GET_CCP_VERSION,
    EXCHANGE_ID,
    SET_MTA,
    DNLOAD,
    UPLOAD,
    GET_DAQ_SIZE,
    SET_DAQ_PTR,
    WRITE_DAQ,
    START_STOP,
    DISCONNECT,
    # Optional Commands
    GET_SEED,
    UNLOCK,
    DNLOAD_6,
    SHORT_UP,
    SELECT_CAL_PAGE,
    SET_S_STATUS,
    GET_S_STATUS,
    BUILD_CHKSUM,
    CLEAR_MEMORY,
    PROGRAM,
    PROGRAM_6,
    MOVE,
    TEST,
    GET_ACTIVE_CAL_PAGE,
    START_STOP_ALL,
    DIAG_SERVICE,
    ACTION_SERVICE,
)

MessageCallback = Callable[[CRO], DTO]


class Client:
    class _Receiver(Thread):
        def __init__(self, client: "Client") -> None:
            super().__init__()
            self._client = client
            self._stop_event = Event()

        def run(self):
            while not self._stop_event.is_set():
                message: Optional[can.Message] = self._client._get_data(timeout=0.1)

                if message is not None:
                    self._client._on_message(message)

        def stop(self) -> None:
            self._stop_event.set()
            self.join()

    class _Sender(Thread):
        def __init__(self, client: "Client") -> None:
            super().__init__()
            self._client = client
            self._stop_event = Event()
            self._queue = Queue()

        def run(self) -> None:
            while not self._stop_event.is_set():
                try:
                    can_msg: Optional[can.Message] = self._queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                except queue.ShutDown:
                    break

                if can_msg is not None:
                    try:
                        self._client._send(can_msg)
                    except can.exceptions.CanError:
                        pass

                self._queue.task_done()

        def stop(self) -> None:
            self._stop_event.set()
            self._queue.shutdown(immediate=True)
            self._queue.join()
            self.join()

    class _DAQSender(_Sender):
        def __init__(self, client: "Client"):
            super().__init__(client)

        def send_daq(self, message: DAQMessage) -> None:
            message = can.Message(arbitration_id=message.daq_id, data=message.bytes())
            self._queue.put(message)

    class _DTOSender(_Sender):
        def __init__(self, client: "Client"):
            super().__init__(client)

        def send_dto(self, message: DTO) -> None:
            message = can.Message(
                arbitration_id=self._client._dto, data=message.bytes()
            )
            self._queue.put(message)

    def __init__(self, bus: can.BusABC, cro: int, dto: int, station_id: int) -> None:
        self.logger = logging.getLogger(__name__)
        self._bus = bus
        self._cro = cro
        self._dto = dto
        self._station_id = station_id
        self._receiver = None
        self._dto_sender: Optional[Client._DTOSender] = None
        self._daq_sender: Optional[Client._DAQSender] = None
        self._send_lock = Lock()
        self._handlers_lock = Lock()
        self._handlers: dict[int, Optional[MessageCallback]] = {
            cmd.code: None for cmd in _SUPPORTED_COMMAND
        }

    def __enter__(self) -> "Client":
        self._receiver = self._Receiver(self)
        self._dto_sender = self._DTOSender(self)
        self._daq_sender = self._DAQSender(self)

        self._dto_sender.start()
        self._daq_sender.start()
        self._receiver.start()

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._receiver is not None:
            self._receiver.stop()
            self._receiver = None
        if self._dto_sender is not None:
            self._dto_sender.stop()
            self._dto_sender = None
        if self._daq_sender is not None:
            self._daq_sender.stop()
            self._daq_sender = None
        if self._bus is not None:
            self._bus.shutdown()
            self._bus = None

    def _get_data(self, timeout: Optional[float] = None) -> Optional[can.Message]:
        """Receive the first available message within `timeout` seconds."""
        if timeout is None:
            return self._bus.recv(timeout=None)

        deadline = time.monotonic() + timeout

        while (residual := deadline - time.monotonic()) > 0:
            message = self._bus.recv(timeout=residual)

            if message is not None:
                return message

        return None

    def _send(self, message: can.Message, timeout: Optional[float] = None) -> None:
        with self._send_lock:
            self._bus.send(message, timeout=timeout)

    def _on_message(self, message: can.Message) -> None:
        """Handle an incoming CAN message."""
        # This method is intended to be overridden by subclasses.
        if message.arbitration_id != self._cro:
            return

        if message.dlc != 8:
            self.logger.warning("Invalid message length")
            return

        cro = CRO(message.data)

        with self._handlers_lock:
            if cro.code not in self._handlers:
                self.logger.warning(f"Invalid CRO: 0x{cro.code:04X}")
                return

            handler = self._handlers.get(cro.code)

            if handler is not None:
                dto = handler(cro)

        if self._dto_sender is not None:
            self._dto_sender.send_dto(dto)

    def register_handler(self, command_code: int, handler: MessageCallback) -> None:
        """Register a handler for a specific command code."""
        with self._handlers_lock:
            if command_code not in self._handlers:
                self.logger.warning(f"Invalid command code: 0x{command_code:04X}")
                return

            self._handlers[command_code] = handler
