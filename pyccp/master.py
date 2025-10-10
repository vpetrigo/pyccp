#!/usr/bin/env python
# -*- coding: utf-8 -*-

__copyright__ = """
    pySART - Simplified AUTOSAR-Toolkit for Python.

   (C) 2009-2016 by Christoph Schueler <cpu12.gems@googlemail.com>

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
from typing import Optional, Union

import can
from can import Message

from pyccp import ccp
from pyccp.ccp import CommandTimeout, SecondaryResource
from pyccp.logger import Logger

MTA0 = 0
MTA1 = 1


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
        Sends a Command Receive Objec (CRO) message via the transport layer.

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
        :return: The updated control byte value after the message is sent.
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

    def get_data(self, timeout=None) -> Optional[Message]:
        start_time = time.time()
        residual_timeout = timeout

        while True:
            if timeout is not None:
                residual_timeout = timeout - (time.time() - start_time)

                if residual_timeout <= 0:
                    break

            message = self.transport.recv(timeout=residual_timeout)

            if message is not None:
                if message.arbitration_id == self._dto:
                    self.logger.debug(f"Received message: {message}")
                    return message
            else:
                self.logger.warn(f"Nothing received after: {timeout} seconds")

        return None

    def _transaction(
        self,
        timeout: CommandTimeout,
        can_id: int,
        command: int,
        ctr: int,
        *data: Union[int, bytes],
    ) -> Optional[bytes]:
        ctr = self.send_cro(can_id, command, ctr, *data)
        response = self.get_data(timeout)
        self.logger.debug(f"Received response: {response}")

        if response is None:
            return None

        if not ccp.verify_ctr(ctr, response.data):
            self.logger.error(
                f"Invalid CTR value: expected {ctr}, received: {response.data[2]}"
            )
            return None

        return response.data

    # Mandatory Commands.
    def connect(self, can_id: int, address: int) -> Optional[bytes]:
        high_address = (address & 0xFF00) >> 8
        low_address = address & 0x00FF
        return self._transaction(
            ccp.CommandTimeout.CONNECT,
            can_id,
            ccp.CommandCodes.CONNECT,
            self.ctr.value,
            low_address,
            high_address,
        )

    def get_ccp_version(self, can_id, major=2, minor=1) -> Optional[bytes]:
        return self._transaction(
            ccp.CommandTimeout.GET_CCP_VERSION,
            can_id,
            ccp.CommandCodes.GET_CCP_VERSION,
            self.ctr.value,
            major,
            minor,
        )

    def exchange_id(
        self, can_id, b0=0, b1=0, b2=0, b3=0, b4=0, b5=0
    ) -> Optional[bytes]:
        return self._transaction(
            ccp.CommandTimeout.EXCHANGE_ID,
            can_id,
            ccp.CommandCodes.EXCHANGE_ID,
            self.ctr.value,
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
        address = struct.pack("<L", address)
        return self._transaction(
            ccp.CommandTimeout.SET_MTA,
            can_id,
            ccp.CommandCodes.SET_MTA,
            self.ctr.value,
            mta,
            address_extension,
            *address,
        )

    def dnload(self, can_id: int, size: int, data: bytes) -> Optional[bytes]:
        return self._transaction(
            ccp.CommandTimeout.DNLOAD,
            can_id,
            ccp.CommandCodes.DNLOAD,
            self.ctr.value,
            size,
            *data,
        )

    def upload(self, can_id, size) -> Optional[bytes]:
        return self._transaction(
            ccp.CommandTimeout.UPLOAD,
            can_id,
            ccp.CommandCodes.UPLOAD,
            self.ctr.value,
            size,
        )

    def get_daq_size(self, can_id, daq_list_number, address) -> Optional[bytes]:
        address = struct.pack(">L", address)
        return self._transaction(
            ccp.CommandTimeout.GET_DAQ_SIZE,
            can_id,
            ccp.CommandCodes.GET_DAQ_SIZE,
            self.ctr.value,
            daq_list_number,
            0x00,
            *address,
        )

    def set_daq_ptr(
        self, can_id, daq_list_number, odt_number, element_number
    ) -> Optional[bytes]:
        return self._transaction(
            ccp.CommandTimeout.SET_DAQ_PTR,
            can_id,
            ccp.CommandCodes.SET_DAQ_PTR,
            self.ctr.value,
            daq_list_number,
            odt_number,
            element_number,
        )

    def write_daq(
        self, can_id, element_size, address_extension, address
    ) -> Optional[bytes]:
        address = struct.pack(">L", address)
        return self._transaction(
            ccp.CommandTimeout.WRITE_DAQ,
            can_id,
            ccp.CommandCodes.WRITE_DAQ,
            self.ctr.value,
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
        rate_prescaler = struct.pack(">H", rate_prescaler)
        return self._transaction(
            ccp.CommandTimeout.START_STOP,
            can_id,
            ccp.CommandCodes.START_STOP,
            self.ctr.value,
            mode,
            daq_list_number,
            last_odt_number,
            event_channel,
            *rate_prescaler,
        )

    def disconnect(
        self, can_id, disconnect_type: ccp.DisconnectType, address
    ) -> Optional[bytes]:
        address = struct.pack("<H", address)
        return self._transaction(
            ccp.CommandTimeout.DISCONNECT,
            can_id,
            ccp.CommandCodes.DISCONNECT,
            self.ctr.value,
            disconnect_type,
            0x00,
            *address,
        )

    # Optional Commands.
    def test(self, can_id):
        pass

    def dnload6(self, can_id, data) -> Optional[bytes]:
        return self._transaction(
            can_id, ccp.CommandCodes.DNLOAD_6, self.ctr.value, *data
        )

    def short_up(self, can_id, size, address, address_extension):
        pass

    def start_stop_all(self, can_id):
        pass

    def set_s_status(self, can_id):
        pass

    def get_s_status(self, can_id):
        pass

    def build_chksum(self, can_id: int, block_size: int) -> Optional[bytes]:
        block_size = struct.pack("<L", block_size)
        return self._transaction(
            ccp.CommandTimeout.BUILD_CHKSUM,
            can_id,
            ccp.CommandCodes.BUILD_CHKSUM,
            self.ctr.value,
            *block_size,
        )

    def clear_memory(self, can_id):
        pass

    def program(self, can_id):
        pass

    def program6(self, can_id):
        pass

    def move(self, can_id):
        pass

    def get_active_cal_page(self, can_id):
        pass

    def select_cal_page(self, can_id):
        pass

    def unlock(self, can_id: int, key: int) -> Optional[bytes]:
        return self._transaction(
            ccp.CommandTimeout.UNLOCK,
            can_id,
            ccp.CommandCodes.UNLOCK,
            self.ctr.value,
            key,
        )

    def get_seed(self, can_id: int, resource: SecondaryResource) -> Optional[bytes]:
        return self._transaction(
            ccp.CommandTimeout.GET_SEED,
            can_id,
            ccp.CommandCodes.GET_SEED,
            self.ctr.value,
            resource,
        )
