#!/usr/bin/env python
# -*- coding: utf-8 -*-

import ctypes
import logging
import struct
import time
from typing import Optional

import can
from can import Message

from . import ccp
from .ccp import SecondaryResource

MTA0 = 0
MTA1 = 1


def _unsigned(name: str, value: int, bits: int) -> int:
    if not isinstance(value, int) or not 0 <= value < (1 << bits):
        raise ValueError(
            f"{name} must be an unsigned {bits}-bit integer, got {value!r}"
        )

    return value


def _payload(data: bytes, minimum: int, maximum: int):
    """Normalize byte sequences without interpreting integers as zero-filled data."""
    if isinstance(data, (int, str)):
        raise TypeError("Data must be a bytes-like object or byte sequence")

    payload = bytes(data)

    if not minimum <= len(payload) <= maximum:
        raise ValueError(
            f"Data length must be between {minimum} and {maximum}, got {len(payload)}"
        )

    return payload


def _transfer_size(size: int):
    if not isinstance(size, int) or not 1 <= size <= 5:
        raise ValueError(f"Size must be between 1 and 5, got {size!r}")

    return size


def _pack_address(address: int):
    return struct.pack("<L", _unsigned("Address", address, 32))


class Master:
    def __init__(self, bus: can.BusABC, cro: int, dto: int):
        """CCP Master implementation for sending and receiving messages over
        a CAN Calibration Protocol.

        :param bus: CAN Bus object for sending and receiving messages.
        :type bus: `can.BusABC`
        :param cro: The 11-bit or 29-bit identifier for outgoing CAN message from
        the host.
        :type cro: int
        :param dto: The 11-bit or 29-bit identifier for incoming CAN message from
        a slave.
        :type dto: int
        """
        self.transport = bus
        self.ctr = ctypes.c_uint8(0)
        self.logger = logging.getLogger(__name__)
        self._cro = cro
        self._dto = dto

    def shutdown(self):
        self.transport.shutdown()

    def send_cro(self, cmd: ccp.Command, ctr, *data: int) -> int:
        """
        Send a Command Receive Object (CRO) message via the transport layer.

        This method constructs the CRO data frame using the provided
        Command Specifier (cmd), counter value (ctr), and additional data bytes.
        The data frame is then sent using the transport layer. It also ensures
        that the control byte value increments properly after each successful
        transmission.

        :param cmd: Command Specifier byte used in the CCP protocol.
        :type cmd: int
        :param ctr: Control byte used for controlling the flow of messages.
        :type ctr: int
        :param data: Up to six additional data bytes for the message payload.
        :return: The transmitted counter (the internal counter advances after sending).
        :rtype: int
        :raises ValueError: If more than six data bytes are provided.
        """
        if len(data) > 6:
            raise ValueError(f"Maximum 6 data bytes allowed, got {len(data)}")

        data = bytearray((cmd.code, ctr, *data))

        if len(data) < ccp.MAX_CRO:
            data.extend(bytearray(ccp.MAX_CRO - len(data)))

        msg = Message(arbitration_id=self._cro, data=data, is_rx=False)
        self.logger.debug(f"Command: [{cmd}]")
        self.logger.debug(f"Sending message: {msg}")
        self.transport.send(msg)
        self.ctr = ctypes.c_uint8(self.ctr.value + 1)

        return ctr

    def _get_data(self, timeout=None) -> Optional[Message]:
        """Receive the first available message within `timeout` seconds."""
        if timeout is None:
            return self.transport.recv(timeout=None)

        deadline = time.monotonic() + timeout

        while True:
            residual = deadline - time.monotonic()

            if residual <= 0:
                return None

            message = self.transport.recv(timeout=residual)

            if message is not None:
                return message

    def get_data(self, timeout=None) -> Optional[Message]:
        """Return the first message addressed to the DTO id within `timeout` seconds."""
        if timeout is None:
            deadline = None
        else:
            deadline = time.monotonic() + timeout

        while True:
            if deadline is None:
                residual = None
            else:
                residual = deadline - time.monotonic()

                if residual <= 0:
                    break

            message = self._get_data(residual)

            if message is None:
                break

            if message.arbitration_id == self._dto:
                self.logger.debug(f"Received message: {message}")
                return message

        self.logger.warning(f"Nothing received after: {timeout} seconds")

        return None

    def get_raw_data(self, timeout=None) -> Optional[Message]:
        return self._get_data(timeout)

    def _transaction(
        self,
        timeout: int,
        command: ccp.Command,
        ctr: int,
        *data: int,
    ) -> Optional[bytes]:
        ctr = self.send_cro(command, ctr, *data)
        # One absolute deadline; CommandTimeout is milliseconds, recv uses seconds.
        deadline = time.monotonic() + timeout / 1000.0

        while True:
            residual = deadline - time.monotonic()

            if residual <= 0:
                return None

            response = self.get_data(residual)

            if response is None or response.data is None:
                return None

            # Reject frames too short to carry a valid CRM.
            if len(response.data) < 8:
                continue

            # Ignore non-CRM frames (e.g. event messages).
            if response.data[0] != ccp.DTO.Type.COMMAND_RETURN_MESSAGE:
                continue

            if not ccp.verify_ctr(ctr, response.data):
                self.logger.error(
                    f"Invalid CTR value: expected {ctr}, received: {response.data[2]}"
                )
                continue

            return bytes(response.data)

    def _execute(self, command: ccp.Command, *payload: int):
        """Resolve transaction metadata once; public commands only encode payloads."""
        return self._transaction(command.timeout, command, self.ctr.value, *payload)

    # Mandatory Commands.
    def connect(self, address: int) -> Optional[bytes]:
        address = struct.pack("<H", _unsigned("Station address", address, 16))
        return self._execute(ccp.CONNECT, *address)

    def get_ccp_version(
        self, major=ccp.CCP_VERSION[0], minor=ccp.CCP_VERSION[1]
    ) -> Optional[bytes]:
        return self._execute(
            ccp.GET_CCP_VERSION,
            major,
            minor,
        )

    def exchange_id(self, info: bytes) -> Optional[bytes]:
        if len(info) > 6:
            raise ValueError(f"Maximum 6 bytes allowed, got {len(info)}")

        return self._execute(ccp.EXCHANGE_ID, *info)

    def set_mta(self, address, address_extension=0x00, mta=MTA0) -> Optional[bytes]:
        address = _pack_address(address)
        _unsigned("Address extension", address_extension, 8)

        if mta not in (MTA0, MTA1):
            raise ValueError(f"MTA must be 0 or 1, got {mta!r}")

        return self._execute(
            ccp.SET_MTA,
            mta,
            address_extension,
            *address,
        )

    def dnload(self, size: int, data: bytes) -> Optional[bytes]:
        _transfer_size(size)
        data = _payload(data, size, size)

        return self._execute(
            ccp.DNLOAD,
            size,
            *data,
        )

    def upload(self, size) -> Optional[bytes]:
        _transfer_size(size)

        return self._execute(
            ccp.UPLOAD,
            size,
        )

    def get_daq_size(self, daq_list_number, address) -> Optional[bytes]:
        address = _pack_address(address)

        return self._execute(
            ccp.GET_DAQ_SIZE,
            daq_list_number,
            0x00,
            *address,
        )

    def set_daq_ptr(
        self, daq_list_number, odt_number, element_number
    ) -> Optional[bytes]:
        return self._execute(
            ccp.SET_DAQ_PTR,
            daq_list_number,
            odt_number,
            element_number,
        )

    def write_daq(self, element_size, address_extension, address) -> Optional[bytes]:
        address = _pack_address(address)
        _unsigned("Address extension", address_extension, 8)
        return self._execute(
            ccp.WRITE_DAQ,
            element_size,
            address_extension,
            *address,
        )

    def start_stop(
        self,
        mode,
        daq_list_number,
        last_odt_number,
        event_channel,
        rate_prescaler,
    ) -> Optional[bytes]:
        rate_prescaler = struct.pack(
            "<H", _unsigned("Rate prescaler", rate_prescaler, 16)
        )

        return self._execute(
            ccp.START_STOP,
            mode,
            daq_list_number,
            last_odt_number,
            event_channel,
            *rate_prescaler,
        )

    def disconnect(
        self, disconnect_type: ccp.DisconnectType, address
    ) -> Optional[bytes]:
        address = struct.pack("<H", _unsigned("Station address", address, 16))

        return self._execute(
            ccp.DISCONNECT,
            disconnect_type,
            0x00,
            *address,
        )

    # Optional Commands.
    def test(self, station_id: int) -> Optional[bytes]:
        to_send = struct.pack("<H", _unsigned("Station address", station_id, 16))

        return self._execute(ccp.TEST, *to_send)

    def dnload6(self, data) -> Optional[bytes]:
        data = _payload(data, 6, 6)
        return self._execute(
            ccp.DNLOAD_6,
            *data,
        )

    def short_up(self, size, address, address_extension=0) -> Optional[bytes]:
        _transfer_size(size)
        address = _pack_address(address)
        _unsigned("Address extension", address_extension, 8)
        return self._execute(
            ccp.SHORT_UP,
            size,
            address_extension,
            *address,
        )

    def start_stop_all(self, mode: int) -> Optional[bytes]:
        return self._execute(
            ccp.START_STOP_ALL,
            mode,
        )

    def set_s_status(self, status) -> Optional[bytes]:
        status = struct.pack("<B", _unsigned("Status", status, 8))

        return self._execute(
            ccp.SET_S_STATUS,
            *status,
        )

    def get_s_status(self) -> Optional[bytes]:
        return self._execute(ccp.GET_S_STATUS)

    def build_chksum(self, block_size: int) -> Optional[bytes]:
        block_size = struct.pack("<L", _unsigned("Block size", block_size, 32))

        return self._execute(
            ccp.BUILD_CHKSUM,
            *block_size,
        )

    def clear_memory(self, block_size: int) -> Optional[bytes]:
        block_size = struct.pack("<L", _unsigned("Block size", block_size, 32))

        return self._execute(
            ccp.CLEAR_MEMORY,
            *block_size,
        )

    def program(self, data: bytes) -> Optional[bytes]:
        """Program 1–5 bytes at MTA0; empty data ends the programming sequence."""
        data = _payload(data, 0, 5)

        return self._execute(
            ccp.PROGRAM,
            len(data),
            *data,
        )

    def program6(self, data: bytes) -> Optional[bytes]:
        """Program exactly six bytes at MTA0, with no size byte or implicit retries."""
        data = _payload(data, 6, 6)

        return self._execute(
            ccp.PROGRAM_6,
            *data,
        )

    def diag_service(
        self, service_number: int, parameters: bytes = b""
    ) -> Optional[bytes]:
        """Run a diagnostic service with up to four-parameter bytes.

        Return the raw CRM (or None on timeout). The slave sets MTA0 to the
        return information; use upload() separately to read that information.
        """
        service_number = struct.pack(
            "<H", _unsigned("Diagnostic service number", service_number, 16)
        )
        parameters = _payload(parameters, 0, 4)

        return self._execute(
            ccp.DIAG_SERVICE,
            *service_number,
            *parameters,
        )

    def move(self, size: int) -> Optional[bytes]:
        size = struct.pack("<L", _unsigned("Size", size, 32))

        return self._execute(ccp.MOVE, *size)

    def get_active_cal_page(self) -> Optional[bytes]:
        return self._execute(ccp.GET_ACTIVE_CAL_PAGE)

    def select_cal_page(self) -> Optional[bytes]:
        return self._execute(ccp.SELECT_CAL_PAGE)

    def unlock(self, key: bytes) -> Optional[bytes]:
        key = _payload(key, 0, 6)
        return self._execute(
            ccp.UNLOCK,
            *key,
        )

    def get_seed(self, resource: SecondaryResource) -> Optional[bytes]:
        return self._execute(
            ccp.GET_SEED,
            resource,
        )
