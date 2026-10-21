import unittest
from unittest.mock import patch

from can import Message

from pyccp import ccp
from pyccp.master import COMMAND_TIMEOUTS, Master
from tests.sequence_support import Clock

C, T = ccp.CommandCodes, ccp.CommandTimeout
CRO, DTO = 0x7E1, 0x815


class FakeBus:
    def __init__(self, clock):
        self.clock = clock
        self.responses = []
        self.sent = []
        self.timeouts = []
        self.send_error = None
        self.closed = False
        self.latency = 0.0

    def send(self, message):
        if self.send_error:
            raise self.send_error
        self.sent.append(message)

    def recv(self, timeout=None):
        self.timeouts.append(timeout)
        if self.responses:
            self.clock.now += self.latency
            return self.responses.pop(0)
        self.clock.now += timeout
        return None

    def shutdown(self):
        self.closed = True


def crm(ctr=0x27, code=0, can_id=DTO):
    return Message(arbitration_id=can_id, data=[0xFF, code, ctr, 0, 0, 0, 0, 0])


class TestMaster(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.bus = FakeBus(self.clock)
        self.master = Master(self.bus, CRO, DTO)
        self.master.ctr.value = 0x27
        self.addCleanup(patch.stopall)
        patch("pyccp.master.time.monotonic", self.clock).start()

    def test_command_wire_regressions(self):
        # Explicit expected byte order/padding, independent of command encoders.
        cases = [
            ("connect", (0x1234,), [0x01, 0x34, 0x12]),
            ("get_ccp_version", (), [0x1B, 2, 1]),
            ("exchange_id", (), [0x17, 0, 0, 0, 0, 0, 0]),
            ("set_mta", (0x12345678, 2, 1), [0x02, 1, 2, 0x78, 0x56, 0x34, 0x12]),
            ("dnload", (5, b"abcde"), [0x03, 5, *b"abcde"]),
            ("upload", (4,), [0x04, 4]),
            ("get_daq_size", (3, 0x01020304), [0x14, 3, 0, 4, 3, 2, 1]),
            ("set_daq_ptr", (3, 5, 2), [0x15, 3, 5, 2]),
            ("write_daq", (2, 1, 0x02004200), [0x16, 2, 1, 0, 0x42, 0, 2]),
            ("start_stop", (1, 3, 7, 2, 0x1234), [0x06, 1, 3, 7, 2, 0x34, 0x12]),
            ("disconnect", (0, 0x0208), [0x07, 0, 0, 8, 2]),
            ("dnload6", (b"abcdef",), [0x23, *b"abcdef"]),
            ("short_up", (5, 0x12345678, 2), [0x0F, 5, 2, 0x78, 0x56, 0x34, 0x12]),
            ("start_stop_all", (1,), [0x08, 1]),
            ("set_s_status", (0x81,), [0x0C, 0x81]),
            ("get_s_status", (), [0x0D]),
            ("build_chksum", (0x12345678,), [0x0E, 0x78, 0x56, 0x34, 0x12]),
            ("clear_memory", (0x12345678,), [0x10, 0x78, 0x56, 0x34, 0x12]),
            ("program", (b"abcde",), [0x18, 5, *b"abcde"]),
            ("program", (b"",), [0x18, 0]),
            ("program6", (b"\0\xffabcd",), [0x22, 0, 0xFF, *b"abcd"]),
            ("diag_service", (0x1234,), [0x20, 0x34, 0x12]),
            (
                "diag_service",
                (0xFFFF, b"\x00\xffab"),
                [0x20, 0xFF, 0xFF, 0, 0xFF, 97, 98],
            ),
            ("get_active_cal_page", (), [0x09]),
            ("select_cal_page", (), [0x11]),
            ("unlock", (b"abcd",), [0x13, *b"abcd"]),
            ("get_seed", (ccp.SecondaryResource.PGM,), [0x12, 0x40]),
        ]
        for name, args, expected in cases:
            with self.subTest(command=name, args=args):
                self.master.ctr.value = 0x27
                response = crm()
                self.bus.responses.append(response)
                reply = getattr(self.master, name)(CRO, *args)
                self.assertIsInstance(reply, bytes)
                self.assertEqual(reply, bytes(response.data))
                frame = self.bus.sent[-1]
                self.assertEqual(frame.arbitration_id, CRO)
                data = bytes([expected[0], 0x27, *expected[1:]]).ljust(8, b"\0")
                self.assertEqual(bytes(frame.data), data)
                self.assertEqual(self.master.ctr.value, 0x28)

    def test_program_payload_forms_and_boundaries(self):
        for size in range(6):
            for factory in (bytes, bytearray, memoryview, list, tuple):
                with self.subTest(size=size, form=factory):
                    data = factory(bytes(range(size)))
                    self.master.program(CRO, data)
                    self.assertEqual(self.bus.sent[-1].data[2], size)
        for factory in (bytes, bytearray, memoryview, list, tuple):
            self.master.program6(CRO, factory(bytes(range(6))))
            self.assertEqual(bytes(self.bus.sent[-1].data[2:]), bytes(range(6)))

    def test_diag_service_parameter_forms_and_boundaries(self):
        for size in range(5):
            for factory in (bytes, bytearray, memoryview, list, tuple):
                with self.subTest(size=size, form=factory):
                    ctr = self.master.ctr.value
                    response = bytes([0xFF, 0, ctr, 0x20, 1, 0, 0, 0])
                    self.bus.responses.append(
                        Message(arbitration_id=DTO, data=response)
                    )
                    self.assertEqual(
                        self.master.diag_service(CRO, 0, factory(bytes(range(size)))),
                        response,
                    )
                    self.assertEqual(
                        bytes(self.bus.sent[-1].data),
                        bytes([0x20, ctr, 0, 0, *range(size)]).ljust(8, b"\0"),
                    )
        # Diagnostic information is not uploaded automatically.
        self.assertEqual(len(self.bus.sent), 25)

    def test_diag_service_error_response_passthrough(self):
        self.bus.responses.append(crm(code=0x32))
        self.assertEqual(self.master.diag_service(CRO, 8), bytes(crm(code=0x32).data))
        self.assertEqual(len(self.bus.sent), 1)

    def test_invalid_input_never_sends_or_advances_counter(self):
        cases = [("program6", (bytes(size),)) for size in range(9) if size != 6]
        cases += [
            ("diag_service", (-1,)),
            ("diag_service", (65536,)),
            ("diag_service", (1.5,)),
            ("diag_service", ("8",)),
            ("diag_service", (8, b"12345")),
            ("program", (b"123456",)),
            ("dnload6", (b"12345",)),
            ("dnload6", (b"1234567",)),
            ("dnload", (2, b"a")),
            ("dnload", (0, b"")),
            ("upload", (0,)),
            ("upload", (6,)),
            ("short_up", (1, -1)),
            ("short_up", (6, 0)),
            ("set_mta", (1 << 32,)),
            ("set_mta", (0, 256)),
            ("set_mta", (0, 0, 2)),
            ("connect", (-1,)),
            ("disconnect", (0, 65536)),
            ("set_s_status", (256,)),
            ("build_chksum", (-1,)),
            ("clear_memory", (1 << 32,)),
        ]
        for name in ("program", "program6", "dnload6"):
            cases.extend(
                (name, (data,)) for data in (6, True, "abcdef", None, [256], [-1])
            )
        cases.extend(
            ("diag_service", (8, data)) for data in (4, True, "abcd", None, [256], [-1])
        )
        for name, args in cases:
            with self.subTest(command=name, args=args):
                with self.assertRaises((TypeError, ValueError)):
                    getattr(self.master, name)(CRO, *args)
                self.assertEqual(self.bus.sent, [])
                self.assertEqual(self.master.ctr.value, 0x27)

    def test_send_failure_does_not_increment_counter(self):
        self.bus.send_error = RuntimeError("send failed")
        with self.assertRaisesRegex(RuntimeError, "send failed"):
            self.master.program6(CRO, bytes(6))
        self.assertEqual(self.master.ctr.value, 0x27)

    def test_counter_rollover_and_error_response_passthrough(self):
        self.master.ctr.value = 0xFF
        self.bus.responses.append(crm(ctr=0xFF, code=0x35))
        self.assertEqual(self.master.program6(CRO, bytes(6))[1], 0x35)
        self.assertEqual(self.master.ctr.value, 0)
        self.bus.responses.append(crm(ctr=0))
        self.assertEqual(self.master.program(CRO, b"")[2], 0)
        self.assertEqual(self.master.ctr.value, 1)

    def test_timeout_values_and_millisecond_conversion(self):
        self.assertEqual(set(COMMAND_TIMEOUTS), set(C))
        for name, args, seconds in (
            ("program6", (bytes(6),), 0.1),
            ("program", (b"",), 0.1),
            ("upload", (1,), 0.025),
            ("diag_service", (8,), 0.5),
            ("clear_memory", (1,), 30.0),
        ):
            with self.subTest(command=name):
                start = self.clock.now
                self.assertIsNone(getattr(self.master, name)(CRO, *args))
                self.assertAlmostEqual(self.clock.now - start, seconds)
                self.assertAlmostEqual(self.bus.timeouts[-1], seconds)
        self.assertEqual(COMMAND_TIMEOUTS[C.PROGRAM_6], T.PROGRAM_6)

    def test_invalid_responses_ignored_until_valid(self):
        self.bus.responses.extend(
            [
                crm(can_id=0x123),
                Message(arbitration_id=DTO, data=[0xFE] * 8),
                crm(ctr=0x28),
                Message(arbitration_id=DTO, data=[0xFF]),
                crm(),
            ]
        )
        self.assertEqual(self.master.program6(CRO, bytes(6)), bytes(crm().data))
        self.assertEqual(len(self.bus.sent), 1)
        self.assertEqual(len(self.bus.timeouts), 5)

    def test_unrelated_traffic_cannot_extend_deadline(self):
        self.bus.latency = 0.01
        self.bus.responses = [crm(can_id=0x123) for _ in range(20)]
        self.assertIsNone(self.master.program6(CRO, bytes(6)))
        self.assertLessEqual(self.clock.now, 0.11)
        self.assertTrue(self.bus.responses)
        self.assertLess(self.bus.timeouts[-1], self.bus.timeouts[0])

    def test_wrong_counter_traffic_cannot_extend_deadline(self):
        self.bus.latency = 0.01
        self.bus.responses = [crm(ctr=0) for _ in range(20)]
        self.assertIsNone(self.master.program6(CRO, bytes(6)))
        self.assertLessEqual(self.clock.now, 0.11)
        self.assertEqual(len(self.bus.sent), 1)

    def test_send_cro_payload_limit_and_shutdown(self):
        with self.assertRaises(ValueError):
            self.master.send_cro(CRO, C.CONNECT, 0, *range(7))
        self.assertEqual(self.master.ctr.value, 0x27)
        self.assertEqual(self.bus.sent, [])
        self.master.shutdown()
        self.assertTrue(self.bus.closed)


if __name__ == "__main__":
    unittest.main()
