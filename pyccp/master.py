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
from typing import Optional

import can
from can import Message

from pyccp import ccp
from pyccp.ccp import SecondaryResource
from pyccp.logger import Logger

MTA0 = 0
MTA1 = 1


class Master(ccp.CRO):
    def __init__(self, bus: can.BusABC):
        self.slaveConnections = {}
        self.transport = bus
        self.ctr = ctypes.c_uint8(0)
        self.logger = Logger("pyccp.master")

    def shutdown(self):
        self.transport.shutdown()

    def send_cro(self, can_id, cmd, ctr, *data: int) -> int:
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

        data = bytes(cmd, ctr, *data)
        msg = Message(arbitration_id=can_id, data=data, is_rx=False)
        self.transport.send(msg)
        self.ctr = ctypes.c_uint8(self.ctr.value + 1)

        return ctr

    def get_data(self, timeout=None) -> Optional[Message]:
        return self.transport.recv(timeout=timeout)

    ##
    ## Mandatory Commands.
    ##
    def connect(self, can_id, address) -> int:
        h = (address & 0xFF00) >> 8
        l = address & 0x00FF
        return self.send_cro(can_id, ccp.CommandCodes.CONNECT, self.ctr.value, l, h)

    def get_ccp_version(self, can_id, major=2, minor=1) -> int:
        return self.send_cro(
            can_id, ccp.CommandCodes.GET_CCP_VERSION, self.ctr.value, major, minor
        )

    def exchange_id(self, can_id, b0=0, b1=0, b2=0, b3=0, b4=0, b5=0) -> int:
        return self.send_cro(
            can_id, ccp.CommandCodes.EXCHANGE_ID, self.ctr.value, b0, b1, b2, b3, b4, b5
        )

    def set_mta(self, can_id, address, address_extension=0x00, mta=MTA0) -> int:
        address = struct.pack("<L", address)
        return self.send_cro(
            can_id,
            ccp.CommandCodes.SET_MTA,
            self.ctr.value,
            mta,
            address_extension,
            *address,
        )

    def dnload(self, can_id, size, data) -> int:
        return self.send_cro(
            can_id, ccp.CommandCodes.DNLOAD, self.ctr.value, size, *data
        )

    def upload(self, can_id, size) -> int:
        return self.send_cro(can_id, ccp.CommandCodes.UPLOAD, self.ctr.value, size)

    def get_daq_size(self, can_id, daq_list_number, address) -> int:
        address = struct.pack(">L", address)
        return self.send_cro(
            can_id,
            ccp.CommandCodes.GET_DAQ_SIZE,
            self.ctr.value,
            daq_list_number,
            0x00,
            *address,
        )

    def set_daq_ptr(self, can_id, daq_list_number, odt_number, element_number) -> int:
        return self.send_cro(
            can_id,
            ccp.CommandCodes.SET_DAQ_PTR,
            self.ctr.value,
            daq_list_number,
            odt_number,
            element_number,
        )

    def write_daq(self, can_id, element_size, address_extension, address) -> int:
        address = struct.pack(">L", address)
        return self.send_cro(
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
    ) -> int:
        rate_prescaler = struct.pack(">H", rate_prescaler)
        return self.send_cro(
            can_id,
            ccp.CommandCodes.START_STOP,
            self.ctr.value,
            mode,
            daq_list_number,
            last_odt_number,
            event_channel,
            *rate_prescaler,
        )

    def disconnect(self, can_id, permanent, address) -> int:
        address = struct.pack("<H", address)
        return self.send_cro(
            can_id,
            ccp.CommandCodes.DISCONNECT,
            self.ctr.value,
            permanent,
            0x00,
            *address,
        )

    ##
    ## Optional Commands.
    ##
    def test(self, can_id):
        pass

    def dnload6(self, can_id, data) -> int:
        return self.send_cro(can_id, ccp.CommandCodes.DNLOAD_6, self.ctr.value, *data)

    def short_up(self, can_id, size, address, address_extension):
        pass

    def start_stop_all(self, can_id):
        pass

    def set_s_status(self, can_id):
        pass

    def get_s_status(self, can_id):
        pass

    def build_chksum(self, can_id: int, block_size: int) -> int:
        block_size = struct.pack("<L", block_size)
        return self.send_cro(
            can_id, ccp.CommandCodes.BUILD_CHKSUM, self.ctr.value, *block_size
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

    def unlock(self, can_id: int, key: int):
        return self.send_cro(can_id, ccp.CommandCodes.UNLOCK, self.ctr.value, key)

    def get_seed(self, can_id: int, resource: SecondaryResource) -> int:
        return self.send_cro(
            can_id, ccp.CommandCodes.GET_SEED, self.ctr.value, resource
        )
