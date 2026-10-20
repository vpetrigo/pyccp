"""CCP 2.1 section 14 (printed pages 45–46): positive/negative sequences."""

import unittest
from unittest.mock import patch

from pyccp.ccp import CommandCodes as C, ReturnCodes as R
from pyccp.master import Master
from tests.sequence_support import (
    CAL,
    DAQ,
    PGM,
    CRO_ID,
    DTO_ID,
    STATION,
    Clock,
    EcuBus,
    Scenarios,
    SequenceFailure,
)


class ExampleSequences(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.addCleanup(patch.stopall)
        patch("pyccp.master.time.monotonic", self.clock).start()

    def peer(self, **kwargs):
        bus = EcuBus(self.clock, **kwargs)
        master = Master(bus, CRO_ID, DTO_ID)
        runner = Scenarios(master, connected=bus.connected)
        return bus, runner

    def test_14_1_login_protected_and_unprotected(self):
        for protected in (0, CAL):
            with self.subTest(protected=protected):
                bus, run = self.peer(protected=protected)
                run.login()
                expected = [C.CONNECT, C.GET_CCP_VERSION, C.EXCHANGE_ID, C.GET_SEED]
                if protected:
                    expected.append(C.UNLOCK)
                    key_message = next(m for m in bus.sent if m.data[0] == C.UNLOCK)
                    self.assertNotEqual(bytes(key_message.data[2:6]), bus.seed)
                self.assertEqual(bus.trace, expected + [C.GET_S_STATUS, C.SET_S_STATUS])
                self.assertTrue(bus.privileges & CAL)
                self.assertEqual(bus.status, 0x81)

    def test_14_1_login_bad_key_version_and_wrong_station(self):
        bus, run = self.peer(protected=CAL)
        with self.assertRaises(SequenceFailure) as failed:
            run.login(derive_key=lambda seed: seed)
        self.assertEqual(failed.exception.code, R.ACCESS_LOCKED)
        self.assertEqual(bus.trace[-1], C.UNLOCK)
        self.assertNotIn(C.SET_S_STATUS, bus.trace)
        self.assertFalse(bus.privileges & CAL)

        bus, run = self.peer()
        bus.version = (3, 0)
        with self.assertRaises(SequenceFailure):
            run.login()
        self.assertEqual(bus.trace, [C.CONNECT, C.GET_CCP_VERSION])

        bus, run = self.peer()
        with self.assertRaises(SequenceFailure) as failed:
            run.connect(STATION + 1)
        self.assertIsNone(failed.exception.code)
        self.assertFalse(bus.connected)
        self.assertEqual(bus.responses, [])
        self.assertAlmostEqual(self.clock.now, 0.025)

    def test_14_2_multichunk_download_and_connected_bypass(self):
        for connected in (False, True):
            for size in (10, 13):
                with self.subTest(connected=connected, size=size):
                    bus, run = self.peer(connected=connected)
                    before = bytes(bus.memory)
                    data = bytes(range(100, 100 + size))
                    run.download(30, data)
                    self.assertEqual(bus.memory[30 : 30 + size], data)
                    self.assertEqual(bus.memory[:30], before[:30])
                    self.assertEqual(bus.memory[30 + size :], before[30 + size :])
                    self.assertEqual(bus.mta, 30 + size)
                    sizes = [m.data[2] for m in bus.sent if m.data[0] == C.DNLOAD]
                    self.assertEqual(sizes, [5, 5] + ([3] if size == 13 else []))
                    self.assertEqual(bus.trace.count(C.CONNECT), int(not connected))
                    self.assertEqual(
                        bus.trace,
                        ([C.CONNECT] if not connected else [])
                        + [C.SET_MTA]
                        + [C.DNLOAD] * len(sizes),
                    )

    def test_14_2_mid_download_abort_preserves_completed_write(self):
        bus, run = self.peer()
        before = bytes(bus.memory)
        bus.faults[C.DNLOAD, 2] = R.ACCESS_DENIED
        with self.assertRaises(SequenceFailure) as failed:
            run.download(30, b"abcdefghijklm")
        self.assertEqual(failed.exception.command, C.DNLOAD)
        self.assertEqual(failed.exception.code, R.ACCESS_DENIED)
        self.assertEqual(bus.memory[30:35], b"abcde")
        self.assertEqual(bus.memory[35:], before[35:])
        self.assertEqual(bus.mta, 35)
        self.assertEqual(bus.trace.count(C.DNLOAD), 2)

    def test_14_3_multichunk_upload_exact_and_partial(self):
        for size in (10, 13):
            bus, run = self.peer(connected=True)
            before = bytes(bus.memory)
            self.assertEqual(run.upload(30, size), before[30 : 30 + size])
            self.assertEqual(bus.mta, 30 + size)
            self.assertEqual(bus.memory, before)
            self.assertNotIn(C.CONNECT, bus.trace)
            sizes = [m.data[2] for m in bus.sent if m.data[0] == C.UPLOAD]
            self.assertEqual(sizes, [5, 5] + ([3] if size == 13 else []))

    def test_14_3_mid_upload_failure_reports_partial_not_success(self):
        bus, run = self.peer()
        bus.faults[C.UPLOAD, 2] = R.ACCESS_DENIED
        with self.assertRaises(SequenceFailure) as failed:
            run.upload(30, 13)
        self.assertEqual(failed.exception.partial, bytes(range(30, 35)))
        self.assertEqual(bus.mta, 35)
        self.assertEqual(bus.trace.count(C.UPLOAD), 2)

    def test_14_4_checksum_match_skips_download_mismatch_updates_multiple_blocks(self):
        bus, run = self.peer()
        original_status = bus.status
        blocks = [(10, bytes(bus.memory[10:17])), (40, b"abcdefgh"), (70, b"xyz")]
        run.calibrate(blocks, page_start=64)
        for address, data in blocks:
            self.assertEqual(bus.memory[address : address + len(data)], data)
        self.assertEqual(bus.trace.count(C.BUILD_CHKSUM), 3)
        self.assertEqual(bus.trace.count(C.DNLOAD), 3)
        # First block matched: no DNLOAD before the second BUILD_CHKSUM.
        second_checksum = [i for i, c in enumerate(bus.trace) if c == C.BUILD_CHKSUM][1]
        self.assertNotIn(C.DNLOAD, bus.trace[:second_checksum])
        self.assertTrue(bus.selected_page)
        self.assertEqual(bus.selected_page_address, 64)
        self.assertEqual(bus.mta, 64)
        self.assertEqual(bus.trace[-3:], [C.SET_MTA, C.SELECT_CAL_PAGE, C.SET_S_STATUS])
        self.assertEqual(bus.status, original_status | CAL)
        self.assertEqual(bus.trace[-2:], [C.SELECT_CAL_PAGE, C.SET_S_STATUS])
        status_bytes = [m.data[2] for m in bus.sent if m.data[0] == C.SET_S_STATUS]
        self.assertEqual(status_bytes, [original_status & ~CAL, original_status | CAL])

    def test_14_4_checksum_download_page_failures_leave_cal_clear(self):
        for command in (C.BUILD_CHKSUM, C.DNLOAD, C.SELECT_CAL_PAGE):
            with self.subTest(command=command):
                bus, run = self.peer()
                bus.faults[command, 1] = R.ACCESS_DENIED
                with self.assertRaises(SequenceFailure):
                    run.calibrate([(40, b"abcdefgh")])
                self.assertEqual(bus.trace[-1], command)
                self.assertEqual(bus.status, 0x80)
                self.assertEqual(bus.trace.count(C.SET_S_STATUS), 1)
                self.assertFalse(bus.selected_page)

    def test_14_4_page_selection_requires_page_start_not_post_download_mta(self):
        bus, run = self.peer()
        run.download(40, b"abcdefgh")
        self.assertEqual(bus.mta, 48)
        with self.assertRaises(SequenceFailure) as failed:
            run.call("select_cal_page")
        self.assertEqual(failed.exception.code, R.PARAMETER_OUT_OF_RANGE)
        self.assertIsNone(bus.selected_page_address)
        run.call("set_mta", 32)
        run.call("select_cal_page")
        self.assertEqual(bus.selected_page_address, 32)

    def test_14_5_unavailable_list_zero_capacity_invalid_id_and_reinitialize(self):
        bus, run = self.peer()
        run.connect()
        reply = run.call("get_daq_size", 1, 0x500)
        self.assertEqual(reply[1:5], bytes([R.ACKNOWLEDGE, 1, 0, 0]))
        with self.assertRaises(SequenceFailure):
            run.configure_daq(daq_list=1)
        self.assertEqual(bus.trace[-1], C.GET_DAQ_SIZE)
        self.assertNotIn(C.SET_DAQ_PTR, bus.trace)
        self.assertNotIn(C.START_STOP, bus.trace)
        self.assertFalse(bus.status & DAQ)
        with self.assertRaises(SequenceFailure) as failed:
            run.call("get_daq_size", 0, 0x501)
        self.assertEqual(failed.exception.code, R.PARAMETER_OUT_OF_RANGE)
        run.configure_daq()
        self.assertTrue(bus.running)
        self.assertTrue(bus.daq)
        reply = run.call("get_daq_size", 0, 0x500)
        self.assertEqual(reply[3:5], b"\x02\x20")
        self.assertFalse(bus.running)
        self.assertEqual(bus.daq, {})
        self.assertIsNone(bus.pointer)

    def test_14_5_daq_configure_before_enable_and_dto_layout(self):
        bus, run = self.peer()
        bus.status = 0x83
        run.configure_daq()
        self.assertEqual(
            bus.trace,
            [
                C.CONNECT,
                C.GET_S_STATUS,
                C.SET_S_STATUS,
                C.GET_DAQ_SIZE,
                C.SET_DAQ_PTR,
                C.WRITE_DAQ,
                C.SET_DAQ_PTR,
                C.WRITE_DAQ,
                C.SET_S_STATUS,
                C.START_STOP,
            ],
        )
        status_bytes = [m.data[2] for m in bus.sent if m.data[0] == C.SET_S_STATUS]
        self.assertEqual(status_bytes, [0x81, 0x83])
        self.assertEqual(bus.daq, {0: {0: (2, 10), 1: (1, 20)}})
        self.assertTrue(bus.running)
        self.assertEqual(bus.daq_dto(), b"\x20\x0a\x0b\x14")

    def test_14_5_invalid_list_pointer_element_capacity_privilege(self):
        cases = [
            ({"daq_list": 1}, None),
            ({"entries": ((2, 0, 1, 10),)}, None),
            ({"entries": ((0, 7, 1, 10),)}, None),
            ({"entries": ((0, 0, 3, 10),)}, None),
            ({"entries": ((0, 0, 4, 10), (0, 1, 4, 20))}, None),
            ({}, DAQ),
        ]
        for kwargs, protection in cases:
            with self.subTest(kwargs=kwargs, protection=protection):
                bus, run = self.peer(protected=protection or 0)
                with self.assertRaises(SequenceFailure):
                    run.configure_daq(**kwargs)
                self.assertNotIn(C.START_STOP, bus.trace)
                self.assertFalse(bus.running)
                self.assertFalse(bus.status & DAQ)

    def test_14_5_write_failure_does_not_enable_or_start(self):
        bus, run = self.peer()
        bus.faults[C.WRITE_DAQ, 2] = R.ACCESS_DENIED
        with self.assertRaises(SequenceFailure):
            run.configure_daq()
        self.assertEqual(bus.daq, {0: {0: (2, 10)}})
        self.assertFalse(bus.status & DAQ)
        self.assertNotIn(C.START_STOP, bus.trace)

    def test_14_6_program_only_and_program6_remainders(self):
        for six in (False, True):
            for size in (5, 6, 7, 11, 12, 13):
                with self.subTest(six=six, size=size):
                    bus, run = self.peer(connected=True)
                    before = bytes(bus.memory)
                    data = bytes((i * 17 + size) & 255 for i in range(size))
                    run.program_block(40, data, use_six=six)
                    self.assertEqual(bus.memory[40 : 40 + size], data)
                    self.assertEqual(bus.memory[:40], before[:40])
                    self.assertEqual(bus.memory[40 + size :], before[40 + size :])
                    self.assertEqual(bus.programmed, data)
                    self.assertEqual(bus.mta, 40 + size)
                    self.assertTrue(bus.finalized)
                    self.assertNotIn(C.CONNECT, bus.trace)
                    self.assertEqual(
                        bytes(bus.sent[-1].data),
                        bytes([C.PROGRAM, len(bus.sent) - 1, 0, 0, 0, 0, 0, 0]),
                    )
                    writes = bus.sent[2:-1]
                    actual = b"".join(
                        bytes(m.data[2:8])
                        if m.data[0] == C.PROGRAM_6
                        else bytes(m.data[3 : 3 + m.data[2]])
                        for m in writes
                    )
                    self.assertEqual(actual, data)
                    self.assertEqual(
                        bus.trace.count(C.PROGRAM_6), size // 6 if six else 0
                    )

    def test_14_6_erase_mid_program_and_finalization_failures(self):
        for command, occurrence in (
            (C.CLEAR_MEMORY, 1),
            (C.PROGRAM, 2),
            (C.PROGRAM, 4),
        ):
            bus, run = self.peer()
            before = bytes(bus.memory)
            bus.faults[command, occurrence] = R.ACCESS_DENIED
            with self.assertRaises(SequenceFailure):
                run.program_block(40, b"abcdefghijklm")
            self.assertFalse(bus.finalized)
            self.assertEqual(bus.trace[-1], command)
            if command == C.CLEAR_MEMORY:
                self.assertFalse(bus.erased)
                self.assertEqual(bus.memory, before)
            elif occurrence == 2:
                self.assertEqual(bus.memory[40:45], b"abcde")
                self.assertEqual(bus.memory[45:53], b"\xff" * 8)
                self.assertEqual(bus.mta, 45)
                self.assertEqual(bus.trace.count(C.PROGRAM), 2)
            else:
                self.assertEqual(bus.memory[40:53], b"abcdefghijklm")
                self.assertEqual(bus.mta, 53)

    def test_14_6_program6_midstream_failure_and_locked_erase(self):
        bus, run = self.peer()
        bus.faults[C.PROGRAM_6, 2] = R.ACCESS_LOCKED
        with self.assertRaises(SequenceFailure):
            run.program_block(40, b"abcdefghijklm", use_six=True)
        self.assertEqual(bus.programmed, b"abcdef")
        self.assertEqual(bus.mta, 46)
        self.assertNotIn(C.PROGRAM, bus.trace)
        self.assertFalse(bus.finalized)
        bus, run = self.peer(protected=PGM)
        with self.assertRaises(SequenceFailure) as failed:
            run.program_block(40, b"abc")
        self.assertEqual(failed.exception.code, R.ACCESS_LOCKED)
        self.assertFalse(bus.erased)

    def test_all_six_sequences_abort_on_c3_and_timeout(self):
        # Execute complete runners: reaching the failure must prevent every later step.
        cases = [
            ("login", (), C.GET_SEED, 1, 0.025),
            ("download", (40, b"abcdefghijklm"), C.DNLOAD, 2, 0.025),
            ("upload", (40, 13), C.UPLOAD, 2, 0.025),
            ("calibrate", ([(40, b"abcdefgh")],), C.BUILD_CHKSUM, 1, 30.0),
            ("configure_daq", (), C.WRITE_DAQ, 2, 0.025),
            ("program_block", (40, b"abcdefghijklm"), C.PROGRAM, 2, 0.1),
        ]
        for name, args, command, occurrence, timeout in cases:
            for code in (R.ACCESS_DENIED, None):
                with self.subTest(sequence=name, code=code):
                    bus, run = self.peer()
                    bus.faults[command, occurrence] = code
                    start = self.clock.now
                    with self.assertRaises(SequenceFailure) as failed:
                        getattr(run, name)(*args)
                    self.assertEqual(failed.exception.command, command)
                    self.assertEqual(failed.exception.code, code)
                    self.assertEqual(bus.trace[-1], command)
                    self.assertEqual(bus.counts[command], occurrence)
                    self.assertFalse(bus.finalized)
                    self.assertFalse(bus.running)
                    if code is None:
                        self.assertAlmostEqual(self.clock.now - start, timeout)
                    else:
                        self.assertEqual(self.clock.now, start)


if __name__ == "__main__":
    unittest.main()
