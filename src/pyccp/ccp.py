#!/usr/bin/env python
# -*- coding: utf-8 -*-

import dataclasses
import enum

MAX_CRO = 0x0008
MAX_DTO = 0x0008

CCP_VERSION = (2, 1)


@dataclasses.dataclass(frozen=True)
class Command:
    """
    Immutable command configuration.

    Represents a command by its numeric code and the timeout value associated
    with executing or handling that command. Instances are frozen by the data class
    declaration, so the recorded values are intended to remain stable after
    creation.

    :ivar code: Numeric identifier for the command.
    :ivar timeout: Timeout value associated with the command in milliseconds.
    """

    code: int
    timeout: int


# Mandatory Commands
CONNECT = Command(0x01, 25)
GET_CCP_VERSION = Command(0x1B, 25)
EXCHANGE_ID = Command(0x17, 25)
SET_MTA = Command(0x02, 25)
DNLOAD = Command(0x03, 25)
UPLOAD = Command(0x04, 25)
GET_DAQ_SIZE = Command(0x14, 25)
SET_DAQ_PTR = Command(0x15, 25)
WRITE_DAQ = Command(0x16, 25)
START_STOP = Command(0x06, 25)
DISCONNECT = Command(0x07, 25)
# Optional Commands
GET_SEED = Command(0x12, 25)
UNLOCK = Command(0x13, 25)
DNLOAD_6 = Command(0x23, 25)
SHORT_UP = Command(0x0F, 25)
SELECT_CAL_PAGE = Command(0x11, 25)
SET_S_STATUS = Command(0x0C, 25)
GET_S_STATUS = Command(0x0D, 25)
BUILD_CHKSUM = Command(0x0E, 30000)
CLEAR_MEMORY = Command(0x10, 30000)
PROGRAM = Command(0x18, 100)
PROGRAM_6 = Command(0x22, 100)
MOVE = Command(0x19, 30000)
TEST = Command(0x05, 25)
GET_ACTIVE_CAL_PAGE = Command(0x09, 25)
START_STOP_ALL = Command(0x08, 25)
DIAG_SERVICE = Command(0x20, 500)
ACTION_SERVICE = Command(0x21, 5000)


class ReturnCodes(enum.IntEnum):
    ACKNOWLEDGE = 0x00
    DAQ_PROCESSOR_OVERLOAD = 0x01  # C0
    COMMAND_PROCESSOR_BUSY = 0x10  # C1 NONE (wait until ACK or timeout)
    DAQ_PROCESSOR_BUSY = 0x11  # C1 NONE (wait until ACK or timeout)
    INTERNAL_TIMEOUT = 0x12  # C1 NONE (wait until ACK or timeout)
    KEY_REQUEST = 0x18  # C1 NONE (embedded seed&key)
    SESSION_STATUS_REQUEST = 0x19  # C1 NONE (embedded SET_S_STATUS)
    COLD_START_REQUEST = 0x20  # C2 COLD START
    CAL_DATA_INIT_REQUEST = 0x21  # C2 cal. data initialization
    DAQ_LIST_INIT_REQUEST = 0x22  # C2 DAQ list initialization
    CODE_UPDATE_REQUEST = 0x23  # C2 (COLD START)
    UNKNOWN_COMMAND = 0x30  # C3 (FAULT)
    COMMAND_SYNTAX = 0x31  # C3 FAULT
    PARAMETER_OUT_OF_RANGE = 0x32  # C3 FAULT
    ACCESS_DENIED = 0x33  # C3 FAULT
    OVERLOAD = 0x34  # C3 FAULT
    ACCESS_LOCKED = 0x35  # C3 FAULT
    RESOURCE_FUNCTION_NOT_AVAILABLE = 0x36  # C3 FAULT


class DisconnectType(enum.IntEnum):
    TEMPORARY = 0x00
    PERMANENT = 0x01


class SecondaryResource(enum.IntEnum):
    """
    Enumeration for secondary resource types.

    This enumeration defines constants representing different types of secondary
    resources that can be used or required in various systems or operations.

    :cvar CAL: Represents the calibration resource.
    :cvar DAQ: Represents the data acquisition resource.
    :cvar PGM: Represents the programming resource.
    """

    CAL = 1 << 0
    DAQ = 1 << 1
    PGM = 1 << 6


class DTO:
    class Type(enum.IntEnum):
        COMMAND_RETURN_MESSAGE = 255
        EVENT_MESSAGE = 254


def verify_ctr(ctr: int, response: bytes) -> bool:
    if len(response) < 3:
        return False

    return ctr == response[2]
