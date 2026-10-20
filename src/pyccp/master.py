#!/usr/bin/env python
# -*- coding: utf-8 -*-

__copyright__ = """
    pySART - Simplified AUTOSAR-Toolkit for Python.

   (C) 2009-2016 by Christoph Schueler <cpu12.gems@googlemail.com>
   (C) 2023-2026 by Vladimir Petrigo <vladimir.petrigo@gmail.com>

   All Rights Reserved

  This program is free software; you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation; either version 2 of the License, or
  (at your option) any later version.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License along
  with this program; if not, write to the Free Software Foundation, Inc.,
  51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""

import ctypes
import struct
import time
from typing import Optional

import can
from can import Message

from . import ccp
from .ccp import CommandTimeout, SecondaryResource
from .logger import Logger

MTA0 = 0
MTA1 = 1

# CommandTimeout is an IntEnum: equal duration values are aliases, so map
# commands explicitly rather than relying on the timeout member's .name.
COMMAND_TIMEOUTS = {
    command: CommandTimeout.__members__[command.name] for command in ccp.CommandCodes
}


def _unsigned(name: str, value: int, bits: int):
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


class Master(ccp.CRO):
    def __init__(self, bus: can.BusABC, cro: int, dto: int):
        self.slaveConnections = {}
        self.transport = bus
        self.ctr = ctypes.c_uint8(0)
        self.logger = Logger("pyccp.master")
        self._cro = cro
        self._dto = dto

    def shutdown(self):
        self.transport.shutdown()

    def send_cro(self, can_id, cmd: ccp.CommandCodes, ctr, *data: int) -> int:
        """
        Send a Command Receive Object (CRO) message via the transport layer.

        This method constructs the CRO data frame using the provided
        Command Specifier (cmd), counter value (ctr), and additional data bytes.
        The data frame is then sent using the transport layer. It also ensures
        that the control byte value increments properly after each successful
        transmission.

        :param can_id: The 11-bit or 29-bit identifier for the CAN message.
        :type can_id: int
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

        data = bytearray((cmd, ctr, *data))

        if len(data) < ccp.MAX_CRO:
            data.extend(bytearray(ccp.MAX_CRO - len(data)))

        msg = Message(arbitration_id=can_id, data=data, is_rx=False)
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

        self.logger.warn(f"Nothing received after: {timeout} seconds")

        return None

    def get_raw_data(self, timeout=None) -> Optional[Message]:
        return self._get_data(timeout)

    def _transaction(
        self,
        timeout: CommandTimeout,
        can_id: int,
        command: ccp.CommandCodes,
        ctr: int,
        *data: int,
    ) -> Optional[bytes]:
        ctr = self.send_cro(can_id, command, ctr, *data)
        # One absolute deadline; CommandTimeout is milliseconds, recv uses seconds.
        deadline = time.monotonic() + float(timeout) / 1000.0

        while True:
            residual = deadline - time.monotonic()

            if residual <= 0:
                return None

            response = self.get_data(residual)

            if response is None:
                return None

            # Reject frames too short to carry a valid CRM.
            if len(response.data) < 8:
                continue

            # Ignore non-CRM frames (e.g. event messages).
            if response.data[0] != ccp.DTOType.COMMAND_RETURN_MESSAGE:
                continue

            if not ccp.verify_ctr(ctr, response.data):
                self.logger.error(
                    f"Invalid CTR value: expected {ctr}, received: {response.data[2]}"
                )
                continue

            return bytes(response.data)

    def _execute(self, command: ccp.CommandCodes, can_id: int, *payload: int):
        """Resolve transaction metadata once; public commands only encode payloads."""
        return self._transaction(
            COMMAND_TIMEOUTS[command], can_id, command, self.ctr.value, *payload
        )

    # Mandatory Commands.
    def connect(self, can_id: int, address: int) -> Optional[bytes]:
        address = struct.pack("<H", _unsigned("Station address", address, 16))
        return self._execute(ccp.CommandCodes.CONNECT, can_id, *address)

    def get_ccp_version(self, can_id, major=2, minor=1) -> Optional[bytes]:
        return self._execute(
            ccp.CommandCodes.GET_CCP_VERSION,
            can_id,
            major,
            minor,
        )

    def exchange_id(
        self, can_id, b0=0, b1=0, b2=0, b3=0, b4=0, b5=0
    ) -> Optional[bytes]:
        return self._execute(
            ccp.CommandCodes.EXCHANGE_ID,
            can_id,
            b0,
            b1,
            b2,
            b3,
            b4,
            b5,
        )

    def set_mta(
        self, can_id, address, address_extension=0x00, mta=MTA0
    ) -> Optional[bytes]:
        address = _pack_address(address)
        _unsigned("Address extension", address_extension, 8)

        if mta not in (MTA0, MTA1):
            raise ValueError(f"MTA must be 0 or 1, got {mta!r}")

        return self._execute(
            ccp.CommandCodes.SET_MTA,
            can_id,
            mta,
            address_extension,
            *address,
        )

    def dnload(self, can_id: int, size: int, data: bytes) -> Optional[bytes]:
        _transfer_size(size)
        data = _payload(data, size, size)

        return self._execute(
            ccp.CommandCodes.DNLOAD,
            can_id,
            size,
            *data,
        )

    def upload(self, can_id, size) -> Optional[bytes]:
        _transfer_size(size)

        return self._execute(
            ccp.CommandCodes.UPLOAD,
            can_id,
            size,
        )

    def get_daq_size(self, can_id, daq_list_number, address) -> Optional[bytes]:
        address = _pack_address(address)

        return self._execute(
            ccp.CommandCodes.GET_DAQ_SIZE,
            can_id,
            daq_list_number,
            0x00,
            *address,
        )

    def set_daq_ptr(
        self, can_id, daq_list_number, odt_number, element_number
    ) -> Optional[bytes]:
        return self._execute(
            ccp.CommandCodes.SET_DAQ_PTR,
            can_id,
            daq_list_number,
            odt_number,
            element_number,
        )

    def write_daq(
        self, can_id, element_size, address_extension, address
    ) -> Optional[bytes]:
        address = _pack_address(address)
        _unsigned("Address extension", address_extension, 8)
        return self._execute(
            ccp.CommandCodes.WRITE_DAQ,
            can_id,
            element_size,
            address_extension,
            *address,
        )

    def start_stop(
        self,
        can_id,
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
            ccp.CommandCodes.START_STOP,
            can_id,
            mode,
            daq_list_number,
            last_odt_number,
            event_channel,
            *rate_prescaler,
        )

    def disconnect(
        self, can_id, disconnect_type: ccp.DisconnectType, address
    ) -> Optional[bytes]:
        address = struct.pack("<H", _unsigned("Station address", address, 16))

        return self._execute(
            ccp.CommandCodes.DISCONNECT,
            can_id,
            disconnect_type,
            0x00,
            *address,
        )

    # Optional Commands.
    def test(self, can_id):
        pass

    def dnload6(self, can_id, data) -> Optional[bytes]:
        data = _payload(data, 6, 6)
        return self._execute(
            ccp.CommandCodes.DNLOAD_6,
            can_id,
            *data,
        )

    def short_up(self, can_id, size, address, address_extension=0):
        _transfer_size(size)
        address = _pack_address(address)
        _unsigned("Address extension", address_extension, 8)
        return self._execute(
            ccp.CommandCodes.SHORT_UP,
            can_id,
            size,
            address_extension,
            *address,
        )

    def start_stop_all(self, can_id: int, mode: int):
        return self._execute(
            ccp.CommandCodes.START_STOP_ALL,
            can_id,
            mode,
        )

    def set_s_status(self, can_id, status):
        _unsigned("Status", status, 8)

        return self._execute(
            ccp.CommandCodes.SET_S_STATUS,
            can_id,
            status,
        )

    def get_s_status(self, can_id):
        return self._execute(
            ccp.CommandCodes.GET_S_STATUS,
            can_id,
        )

    def build_chksum(self, can_id: int, block_size: int) -> Optional[bytes]:
        block_size = struct.pack("<L", _unsigned("Block size", block_size, 32))

        return self._execute(
            ccp.CommandCodes.BUILD_CHKSUM,
            can_id,
            *block_size,
        )

    def clear_memory(self, can_id, block_size):
        block_size = struct.pack("<L", _unsigned("Block size", block_size, 32))

        return self._execute(
            ccp.CommandCodes.CLEAR_MEMORY,
            can_id,
            *block_size,
        )

    def program(self, can_id: int, data: bytes) -> Optional[bytes]:
        """Program 1–5 bytes at MTA0; empty data ends the programming sequence."""
        data = _payload(data, 0, 5)

        return self._execute(
            ccp.CommandCodes.PROGRAM,
            can_id,
            len(data),
            *data,
        )

    def program6(self, can_id: int, data: bytes) -> Optional[bytes]:
        """Program exactly six bytes at MTA0, with no size byte or implicit retries."""
        data = _payload(data, 6, 6)

        return self._execute(
            ccp.CommandCodes.PROGRAM_6,
            can_id,
            *data,
        )

    def move(self, can_id):
        pass

    def get_active_cal_page(self, can_id):
        return self._execute(
            ccp.CommandCodes.GET_ACTIVE_CAL_PAGE,
            can_id,
        )

    def select_cal_page(self, can_id):
        return self._execute(
            ccp.CommandCodes.SELECT_CAL_PAGE,
            can_id,
        )

    def unlock(self, can_id: int, key: bytes) -> Optional[bytes]:
        key = _payload(key, 0, 6)
        return self._execute(
            ccp.CommandCodes.UNLOCK,
            can_id,
            *key,
        )

    def get_seed(self, can_id: int, resource: SecondaryResource) -> Optional[bytes]:
        return self._execute(
            ccp.CommandCodes.GET_SEED,
            can_id,
            resource,
        )
