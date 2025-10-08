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
import enum
import struct
from collections import namedtuple
from pprint import pprint
from typing import Optional

from can import Message
from pyccp import ccp
from pyccp.logger import Logger

MTA0 = 0
MTA1 = 1


class Master(ccp.CRO):
    def __init__(self, bus):
        self.slaveConnections = {}
        self.transport: can.Bus = bus
        self.ctr = ctypes.c_uint8(0)
        self.logger = Logger("pyccp.master")

    def shutdown(self):
        self.transport.shutdown()

    def sendCRO(self, canID, cmd, ctr, b0=0, b1=0, b2=0, b3=0, b4=0, b5=0) -> int:
        """Transfer up to 6 data bytes from master to slave (ECU).

        :return: Operation CTR value
        :rtype: int
        """
        data = (cmd, ctr, b0, b1, b2, b3, b4, b5)
        msg = Message(arbitration_id=canID, data=data, is_rx=False)
        self.transport.send(msg)
        self.ctr = ctypes.c_uint8(self.ctr.value + 1)

        return ctr

    def get_data(self, timeout=None) -> Optional[Message]:
        return self.transport.recv(timeout=timeout)

    ##
    ## Mandatory Commands.
    ##
    def connect(self, canID, address) -> int:
        h = (address & 0xFF00) >> 8
        l = address & 0x00FF
        return self.sendCRO(canID, ccp.CommandCodes.CONNECT, self.ctr.value, l, h)

    def getCCPVersion(self, canID, major=2, minor=1) -> int:
        return self.sendCRO(
            canID, ccp.CommandCodes.GET_CCP_VERSION, self.ctr.value, major, minor
        )

    def exchangeId(self, canID, b0=0, b1=0, b2=0, b3=0, b4=0, b5=0) -> int:
        return self.sendCRO(
            canID, ccp.CommandCodes.EXCHANGE_ID, self.ctr.value, b0, b1, b2, b3, b4, b5
        )

    def setMta(self, canID, address, addressExtension=0x00, mta=MTA0) -> int:
        address = struct.pack("<L", address)
        return self.sendCRO(
            canID,
            ccp.CommandCodes.SET_MTA,
            self.ctr.value,
            mta,
            addressExtension,
            *address
        )

    def dnload(self, canID, size, data) -> int:
        return self.sendCRO(canID, ccp.CommandCodes.DNLOAD, self.ctr.value, size, *data)

    def upload(self, canID, size) -> int:
        return self.sendCRO(canID, ccp.CommandCodes.UPLOAD, self.ctr.value, size)

    def getDaqSize(self, canID, daqListNumber, address) -> int:
        address = struct.pack(">L", address)
        return self.sendCRO(
            canID,
            ccp.CommandCodes.GET_DAQ_SIZE,
            self.ctr.value,
            daqListNumber,
            0x00,
            *address
        )

    def setDaqPtr(self, canID, daqListNumber, odtNumber, elementNumber) -> int:
        return self.sendCRO(
            canID,
            ccp.CommandCodes.SET_DAQ_PTR,
            self.ctr.value,
            daqListNumber,
            odtNumber,
            elementNumber,
        )

    def writeDaq(self, canID, elementSize, addressExtension, address) -> int:
        address = struct.pack(">L", address)
        return self.sendCRO(
            canID,
            ccp.CommandCodes.WRITE_DAQ,
            self.ctr.value,
            elementSize,
            addressExtension,
            *address
        )

    def startStop(
        self, canID, mode, daqListNumber, lastOdtNumber, eventChannel, ratePrescaler
    ) -> int:
        ratePrescaler = struct.pack(">H", ratePrescaler)
        return self.sendCRO(
            canID,
            ccp.CommandCodes.START_STOP,
            self.ctr.value,
            mode,
            daqListNumber,
            lastOdtNumber,
            eventChannel,
            *ratePrescaler
        )

    def disconnect(self, canID, permanent, address) -> int:
        address = struct.pack("<H", address)
        return self.sendCRO(
            canID,
            ccp.CommandCodes.DISCONNECT,
            self.ctr.value,
            permanent,
            0x00,
            *address
        )

    ##
    ## Optional Commands.
    ##
    def test(self, canID):
        pass

    def dnload6(self, canID, data) -> int:
        return self.sendCRO(canID, ccp.CommandCodes.DNLOAD_6, self.ctr.value, *data)

    def shortUp(self, canID, size, address, addressExtension):
        pass

    def startStopAll(self, canID):
        pass

    def setSStatus(self, canID):
        pass

    def getSStatus(self, canID):
        pass

    def buildChksum(self, can_id: int, block_size: int) -> int:
        block_size = struct.pack("<L", block_size)
        return self.sendCRO(
            can_id, ccp.CommandCodes.BUILD_CHKSUM, self.ctr.value, *block_size
        )

    def clearMemory(self, canID):
        pass

    def program(self, canID):
        pass

    def program6(self, canID):
        pass

    def move(self, canID):
        pass

    def getActiveCalPage(self, canID):
        pass

    def selectCalPage(self, canID):
        pass

    def unlock(self, canID):
        pass

    def getSeed(self, canID):
        pass
