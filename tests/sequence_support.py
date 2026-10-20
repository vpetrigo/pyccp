"""Test-only CCP peer and Section 14 runners; not a production slave/workflow API.

The fixture is little-endian. Seed/key and checksum algorithms are test policies.
Only the subset of ECU behavior exercised by the example sequences is modeled.
"""

from collections import Counter

from can import Message

from pyccp.ccp import CommandCodes as C, ReturnCodes as R

CRO_ID, DTO_ID, STATION = 0x7E1, 0x815, 0x1234
CAL, DAQ, PGM = 1, 2, 0x40


def key_for(seed):
    return bytes(value ^ 0xA5 for value in seed)


def checksum(data):
    return sum(data).to_bytes(4, "little")


def uint(data):
    return int.from_bytes(data, "little")


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class EcuBus:
    """Decode actual CROs, with occurrence-based faults before side effects.

    faults[(command, occurrence)] = return code, or None to drop the request.
    Dropped requests do NOT model the ambiguity of a lost reply after a write.
    """

    def __init__(self, clock, connected=False, protected=0):
        self.clock = clock
        self.connected = connected
        self.protected = protected
        self.privileges = (CAL | DAQ | PGM) & ~protected
        self.status = 0x81
        self.version = (2, 1)
        self.seed = b"\x12\x34\x56\x78"
        self.requested = 0
        self.memory = bytearray(range(256)) * 4
        self.mta = 0
        self.extension = 0
        self.selected_page = False
        self.selected_page_address = None
        self.calibration_pages = {32, 64}
        self.erased = False
        self.finalized = False
        self.programmed = bytearray()
        self.daq_capacity = 2  # ODTs in list 0, not number of DAQ lists.
        self.daq = {}
        self.pointer = None
        self.running = False
        self.sent = []
        self.responses = []
        self.counts = Counter()
        self.faults = {}
        self.timeouts = []

    @property
    def trace(self):
        return [C(message.data[0]) for message in self.sent]

    def send(self, message):
        self.sent.append(message)
        assert message.arbitration_id == CRO_ID
        assert len(message.data) == 8
        command, ctr = C(message.data[0]), message.data[1]
        self.counts[command] += 1
        fault_key = (command, self.counts[command])
        if fault_key in self.faults:
            code = self.faults[fault_key]
            if code is None:
                return
            tail = b""
        elif command == C.CONNECT and uint(message.data[2:4]) != STATION:
            return  # A station that is not addressed must remain silent.
        else:
            code, tail = self.execute(command, bytes(message.data[2:]))
        data = bytes([0xFF, code, ctr]) + bytes(tail)
        assert len(data) <= 8
        self.responses.append(Message(arbitration_id=DTO_ID, data=data.ljust(8, b"\0")))

    def recv(self, timeout=None):
        self.timeouts.append(timeout)
        if self.responses:
            return self.responses.pop(0)
        assert timeout is not None
        self.clock.now += timeout
        return None

    def shutdown(self):
        pass

    def address_reply(self):
        return bytes([self.extension]) + self.mta.to_bytes(4, "little")

    def accessible(self, address, size):
        return 0 <= address <= len(self.memory) and address + size <= len(self.memory)

    def execute(self, command, p):
        if command == C.CONNECT:
            self.connected = True
        elif not self.connected:
            return R.ACCESS_DENIED, b""
        elif command == C.GET_CCP_VERSION:
            return R.ACKNOWLEDGE, bytes(self.version)
        elif command == C.EXCHANGE_ID:
            return R.ACKNOWLEDGE, bytes([0, 0, CAL | DAQ | PGM, self.protected])
        elif command == C.GET_SEED:
            if p[0] not in (CAL, DAQ, PGM):
                return R.PARAMETER_OUT_OF_RANGE, b""
            self.requested = p[0]
            locked = bool(self.protected & p[0] & ~self.privileges)
            return R.ACKNOWLEDGE, bytes([locked]) + self.seed
        elif command == C.UNLOCK:
            if not self.requested or p[:4] != key_for(self.seed):
                return R.ACCESS_LOCKED, b""
            self.privileges |= self.requested
            return R.ACKNOWLEDGE, bytes([self.privileges])
        elif command == C.GET_S_STATUS:
            return R.ACKNOWLEDGE, bytes([self.status, 0])
        elif command == C.SET_S_STATUS:
            if p[0] & (CAL | DAQ) & ~self.privileges:
                return R.ACCESS_DENIED, b""
            self.status = p[0]
        elif command == C.SET_MTA:
            if p[0] != 0 or p[1] != 0 or not self.accessible(uint(p[2:6]), 0):
                return R.PARAMETER_OUT_OF_RANGE, b""
            self.mta, self.extension = uint(p[2:6]), p[1]
        elif command in (C.DNLOAD, C.UPLOAD, C.PROGRAM, C.PROGRAM_6):
            programming = command in (C.PROGRAM, C.PROGRAM_6)
            resource = PGM if programming else CAL
            if not self.privileges & resource:
                return R.ACCESS_LOCKED, b""
            size = 6 if command == C.PROGRAM_6 else p[0]
            minimum = 0 if command == C.PROGRAM else 1
            maximum = 6 if command == C.PROGRAM_6 else 5
            if not minimum <= size <= maximum or not self.accessible(self.mta, size):
                return R.PARAMETER_OUT_OF_RANGE, b""
            if programming and not self.erased:
                return R.ACCESS_DENIED, b""
            if command == C.PROGRAM and size == 0:
                self.finalized = True
                return R.ACKNOWLEDGE, self.address_reply()
            if command == C.UPLOAD:
                tail = self.memory[self.mta : self.mta + size]
            else:
                data = p[:6] if command == C.PROGRAM_6 else p[1 : 1 + size]
                self.memory[self.mta : self.mta + size] = data
                if programming:
                    self.programmed.extend(data)
                tail = None
            self.mta += size
            return R.ACKNOWLEDGE, tail if tail is not None else self.address_reply()
        elif command == C.BUILD_CHKSUM:
            size = uint(p[:4])
            if not self.accessible(self.mta, size):
                return R.PARAMETER_OUT_OF_RANGE, b""
            return R.ACKNOWLEDGE, b"\x04" + checksum(
                self.memory[self.mta : self.mta + size]
            )
        elif command == C.SELECT_CAL_PAGE:
            if not self.privileges & CAL:
                return R.ACCESS_LOCKED, b""
            if self.extension or self.mta not in self.calibration_pages:
                return R.PARAMETER_OUT_OF_RANGE, b""
            self.selected_page = True
            self.selected_page_address = self.mta
        elif command == C.GET_DAQ_SIZE:
            if not self.privileges & DAQ:
                return R.ACCESS_LOCKED, b""
            if p[0] != 0:
                return R.ACKNOWLEDGE, b"\x00\x00"
            if uint(p[2:]) != 0x500:
                return R.PARAMETER_OUT_OF_RANGE, b""
            self.running = False
            self.daq.clear()
            self.pointer = None
            return R.ACKNOWLEDGE, bytes([self.daq_capacity, 0x20])
        elif command == C.SET_DAQ_PTR:
            daq_list, odt, element = p[:3]
            if daq_list != 0 or odt >= self.daq_capacity or element >= 7:
                return R.PARAMETER_OUT_OF_RANGE, b""
            self.pointer = (odt, element)
        elif command == C.WRITE_DAQ:
            if not self.privileges & DAQ:
                return R.ACCESS_LOCKED, b""
            size, extension, address = p[0], p[1], uint(p[2:])
            if (
                self.pointer is None
                or size not in (1, 2, 4)
                or extension
                or not self.accessible(address, size)
            ):
                return R.PARAMETER_OUT_OF_RANGE, b""
            odt, element = self.pointer
            entries = dict(self.daq.get(odt, {}))
            entries[element] = (size, address)
            if sum(entry[0] for entry in entries.values()) > 7:
                return R.PARAMETER_OUT_OF_RANGE, b""
            self.daq[odt] = entries
        elif command == C.START_STOP:
            if p[0] != 1 or p[1] != 0 or p[2] >= self.daq_capacity or not uint(p[4:]):
                return R.PARAMETER_OUT_OF_RANGE, b""
            if not self.status & DAQ or any(
                not self.daq.get(odt) for odt in range(p[2] + 1)
            ):
                return R.DAQ_LIST_INIT_REQUEST, b""
            self.running = True
        elif command == C.CLEAR_MEMORY:
            size = uint(p[:4])
            if not self.privileges & PGM:
                return R.ACCESS_LOCKED, b""
            if not self.accessible(self.mta, size):
                return R.PARAMETER_OUT_OF_RANGE, b""
            self.memory[self.mta : self.mta + size] = b"\xff" * size
            self.erased, self.finalized = True, False
            self.programmed.clear()
        else:
            return R.UNKNOWN_COMMAND, b""
        return R.ACKNOWLEDGE, b""

    def daq_dto(self, odt=0):
        assert self.running
        data = b"".join(
            bytes(self.memory[address : address + size])
            for _, (size, address) in sorted(self.daq[odt].items())
        )
        return bytes([0x20 + odt]) + data


class SequenceFailure(Exception):
    def __init__(self, command, code=None, partial=b""):
        self.command, self.code, self.partial = command, code, bytes(partial)
        super().__init__(f"{command.name}: {'timeout' if code is None else hex(code)}")


class Scenarios:
    """Example orchestration policies in tests, deliberately not production API."""

    def __init__(self, master, connected=False):
        self.master = master
        self.connected = connected

    def call(self, name, *args):
        command = C[{"program6": "PROGRAM_6"}.get(name, name.upper())]
        reply = getattr(self.master, name)(CRO_ID, *args)
        if reply is None or reply[1] != R.ACKNOWLEDGE:
            raise SequenceFailure(command, None if reply is None else reply[1])
        return bytes(reply)

    def connect(self, station=STATION):
        if not self.connected:
            self.call("connect", station)
            self.connected = True

    def login(self, resource=CAL, derive_key=key_for):
        self.connect()
        version = self.call("get_ccp_version")[3:5]
        if version != bytes([2, 1]):
            raise SequenceFailure(C.GET_CCP_VERSION, R.PARAMETER_OUT_OF_RANGE)
        self.call("exchange_id")
        reply = self.call("get_seed", resource)
        if reply[3]:
            self.call("unlock", derive_key(reply[4:8]))
        status = self.call("get_s_status")[3]
        if resource in (CAL, DAQ):
            self.call("set_s_status", status | resource)

    def download(self, address, data):
        self.connect()
        self.call("set_mta", address)
        for offset in range(0, len(data), 5):
            chunk = data[offset : offset + 5]
            self.call("dnload", len(chunk), chunk)

    def upload(self, address, size):
        self.connect()
        self.call("set_mta", address)
        data = bytearray()
        try:
            for offset in range(0, size, 5):
                count = min(5, size - offset)
                data.extend(self.call("upload", count)[3 : 3 + count])
        except SequenceFailure as error:
            error.partial = bytes(data)
            raise
        return bytes(data)

    def calibrate(self, blocks, page_start=32):
        self.connect()
        status = self.call("get_s_status")[3] & ~CAL
        self.call("set_s_status", status)
        for address, block in blocks:
            self.call("set_mta", address)
            reply = self.call("build_chksum", len(block))
            if reply[3] != 4 or reply[4:8] != checksum(block):
                self.download(address, block)
        self.call("set_mta", page_start)
        self.call("select_cal_page")
        self.call("set_s_status", status | CAL)

    def configure_daq(self, entries=((0, 0, 2, 10), (0, 1, 1, 20)), daq_list=0):
        self.connect()
        status = self.call("get_s_status")[3] & ~DAQ
        self.call("set_s_status", status)
        capacity = self.call("get_daq_size", daq_list, 0x500)[3]
        last = max(entry[0] for entry in entries)
        if last >= capacity:
            raise SequenceFailure(C.GET_DAQ_SIZE, R.PARAMETER_OUT_OF_RANGE)
        for odt, element, size, address in entries:
            self.call("set_daq_ptr", daq_list, odt, element)
            self.call("write_daq", size, 0, address)
        self.call("set_s_status", status | DAQ)
        self.call("start_stop", 1, daq_list, last, 1, 1)

    def program_block(self, address, data, use_six=False):
        self.connect()
        self.call("set_mta", address)
        self.call("clear_memory", len(data))
        offset = 0
        while offset < len(data):
            if use_six and len(data) - offset >= 6:
                self.call("program6", data[offset : offset + 6])
                offset += 6
            else:
                chunk = data[offset : offset + 5]
                self.call("program", chunk)
                offset += len(chunk)
        self.call("program", b"")
