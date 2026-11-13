"""Fail-scenario tests — CCP 2.1 error-code matrix (Section 16.1).

Tests that the Master correctly receives and reports non-ACK return codes
from the slave for various commands.
"""

import unittest

from pyccp import ccp
from pyccp.ccp import ReturnCodes
from tests.virtual_bus import STATION, make_master_and_slave


class TestErrorCodes(unittest.TestCase):
    """Tests for error return codes from the CCP 2.1 error-code matrix."""

    def _cleanup(self, master, slave):
        """Stop slave thread and shut down both buses."""
        slave.stop()
        master.__exit__(None, None, None)

    # ---- CONNECT errors ----

    def test_connect_access_denied(self):
        """CONNECT: session currently not possible -> ACCESS_DENIED (0x33)."""

        def reply(ctr, cmd, payload):
            return 0x33, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.connect(STATION)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACCESS_DENIED)
        finally:
            self._cleanup(master, slave)

    def test_connect_parameter_out_of_range(self):
        """CONNECT: invalid station address -> PARAMETER_OUT_OF_RANGE (0x32)."""

        def reply(ctr, cmd, payload):
            return 0x32, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.connect(STATION)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.PARAMETER_OUT_OF_RANGE)
        finally:
            self._cleanup(master, slave)

    # ---- SET_MTA errors ----

    def test_set_mta_parameter_out_of_range(self):
        """SET_MTA: illegal MTA#, base address, address ext -> 0x32."""

        def reply(ctr, cmd, payload):
            return 0x32, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.set_mta(0xFFFFFFFF)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.PARAMETER_OUT_OF_RANGE)
        finally:
            self._cleanup(master, slave)

    # ---- DNLOAD errors ----

    def test_dnload_access_denied(self):
        """DNLOAD: write attempt to ROM -> ACCESS_DENIED (0x33)."""

        def reply(ctr, cmd, payload):
            return 0x33, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.dnload(5, b"abcde")
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACCESS_DENIED)
        finally:
            self._cleanup(master, slave)

    def test_dnload_parameter_out_of_range(self):
        """DNLOAD: data block size > 5 -> PARAMETER_OUT_OF_RANGE (0x32)."""

        def reply(ctr, cmd, payload):
            return 0x32, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.dnload(5, b"abcde")
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.PARAMETER_OUT_OF_RANGE)
        finally:
            self._cleanup(master, slave)

    def test_dnload_access_locked(self):
        """DNLOAD: access locked (CAL not unlocked) -> 0x35."""

        def reply(ctr, cmd, payload):
            return 0x35, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.dnload(5, b"abcde")
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACCESS_LOCKED)
        finally:
            self._cleanup(master, slave)

    # ---- DNLOAD_6 errors ----

    def test_dnload6_access_denied(self):
        """DNLOAD_6: write attempt to ROM -> ACCESS_DENIED (0x33)."""

        def reply(ctr, cmd, payload):
            return 0x33, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.dnload6(b"abcdef")
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACCESS_DENIED)
        finally:
            self._cleanup(master, slave)

    # ---- UPLOAD errors ----

    def test_upload_access_denied(self):
        """UPLOAD: upload of classified data -> ACCESS_DENIED (0x33)."""

        def reply(ctr, cmd, payload):
            return 0x33, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.upload(4)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACCESS_DENIED)
        finally:
            self._cleanup(master, slave)

    def test_upload_parameter_out_of_range(self):
        """UPLOAD: data block size > 5 -> PARAMETER_OUT_OF_RANGE (0x32)."""

        def reply(ctr, cmd, payload):
            return 0x32, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.upload(4)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.PARAMETER_OUT_OF_RANGE)
        finally:
            self._cleanup(master, slave)

    # ---- SHORT_UP errors ----

    def test_short_up_access_denied(self):
        """SHORT_UP: upload of classified data -> ACCESS_DENIED (0x33)."""

        def reply(ctr, cmd, payload):
            return 0x33, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.short_up(4, 0x1000)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACCESS_DENIED)
        finally:
            self._cleanup(master, slave)

    def test_short_up_parameter_out_of_range(self):
        """SHORT_UP: block size > 5, illegal base addr -> 0x32."""

        def reply(ctr, cmd, payload):
            return 0x32, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.short_up(4, 0x1000)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.PARAMETER_OUT_OF_RANGE)
        finally:
            self._cleanup(master, slave)

    # ---- SELECT_CAL_PAGE errors ----

    def test_select_cal_page_access_denied(self):
        """SELECT_CAL_PAGE: currently not possible -> ACCESS_DENIED (0x33)."""

        def reply(ctr, cmd, payload):
            return 0x33, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.select_cal_page()
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACCESS_DENIED)
        finally:
            self._cleanup(master, slave)

    # ---- GET_DAQ_SIZE errors ----

    def test_get_daq_size_access_locked(self):
        """GET_DAQ_SIZE: no DAQ privilege level -> ACCESS_LOCKED (0x35)."""

        def reply(ctr, cmd, payload):
            return 0x35, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.get_daq_size(0, 0x500)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACCESS_LOCKED)
        finally:
            self._cleanup(master, slave)

    def test_get_daq_size_parameter_out_of_range(self):
        """GET_DAQ_SIZE: illegal DAQ list number -> 0x32."""

        def reply(ctr, cmd, payload):
            return 0x32, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.get_daq_size(99, 0x500)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.PARAMETER_OUT_OF_RANGE)
        finally:
            self._cleanup(master, slave)

    # ---- SET_DAQ_PTR errors ----

    def test_set_daq_ptr_access_locked(self):
        """SET_DAQ_PTR: no DAQ privilege level -> ACCESS_LOCKED (0x35)."""

        def reply(ctr, cmd, payload):
            return 0x35, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.set_daq_ptr(0, 0, 0)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACCESS_LOCKED)
        finally:
            self._cleanup(master, slave)

    def test_set_daq_ptr_parameter_out_of_range(self):
        """SET_DAQ_PTR: unknown DAQ list, illegal ODT# -> 0x32."""

        def reply(ctr, cmd, payload):
            return 0x32, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.set_daq_ptr(99, 0, 0)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.PARAMETER_OUT_OF_RANGE)
        finally:
            self._cleanup(master, slave)

    # ---- WRITE_DAQ errors ----

    def test_write_daq_access_locked(self):
        """WRITE_DAQ: no DAQ privilege level -> ACCESS_LOCKED (0x35)."""

        def reply(ctr, cmd, payload):
            return 0x35, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.write_daq(2, 0, 0x1000)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACCESS_LOCKED)
        finally:
            self._cleanup(master, slave)

    def test_write_daq_parameter_out_of_range(self):
        """WRITE_DAQ: illegal size of ODT element/addr -> 0x32."""

        def reply(ctr, cmd, payload):
            return 0x32, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.write_daq(2, 0, 0x1000)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.PARAMETER_OUT_OF_RANGE)
        finally:
            self._cleanup(master, slave)

    # ---- START_STOP errors ----

    def test_start_stop_parameter_out_of_range(self):
        """START_STOP: illegal last ODT/line transm. interval -> 0x32."""

        def reply(ctr, cmd, payload):
            return 0x32, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.start_stop(1, 0, 1, 1, 100)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.PARAMETER_OUT_OF_RANGE)
        finally:
            self._cleanup(master, slave)

    def test_start_stop_daq_list_init_request(self):
        """START_STOP: starting DAQ of unconfigured list -> 0x22."""

        def reply(ctr, cmd, payload):
            return 0x22, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.start_stop(1, 0, 1, 1, 100)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.DAQ_LIST_INIT_REQUEST)
        finally:
            self._cleanup(master, slave)

    # ---- DISCONNECT errors ----

    def test_disconnect_access_denied(self):
        """DISCONNECT: temporary disconnect not possible -> 0x33."""

        def reply(ctr, cmd, payload):
            return 0x33, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.disconnect(ccp.DisconnectType.TEMPORARY, STATION)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACCESS_DENIED)
        finally:
            self._cleanup(master, slave)

    def test_disconnect_parameter_out_of_range(self):
        """DISCONNECT: invalid station address -> 0x32."""

        def reply(ctr, cmd, payload):
            return 0x32, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.disconnect(ccp.DisconnectType.PERMANENT, STATION)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.PARAMETER_OUT_OF_RANGE)
        finally:
            self._cleanup(master, slave)

    # ---- SET_S_STATUS errors ----

    def test_set_s_status_access_denied(self):
        """SET_S_STATUS: status bits violate master privilege level -> 0x33."""

        def reply(ctr, cmd, payload):
            return 0x33, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.set_s_status(0x81)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACCESS_DENIED)
        finally:
            self._cleanup(master, slave)

    def test_set_s_status_parameter_out_of_range(self):
        """SET_S_STATUS: currently illegal combination -> 0x32."""

        def reply(ctr, cmd, payload):
            return 0x32, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.set_s_status(0xFF)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.PARAMETER_OUT_OF_RANGE)
        finally:
            self._cleanup(master, slave)

    # ---- GET_S_STATUS errors ----

    def test_get_s_status_access_denied(self):
        """GET_S_STATUS: session status not accessible -> 0x33."""

        def reply(ctr, cmd, payload):
            return 0x33, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.get_s_status()
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACCESS_DENIED)
        finally:
            self._cleanup(master, slave)

    # ---- UNLOCK errors ----

    def test_unlock_access_locked(self):
        """UNLOCK: unqualified key -> ACCESS_LOCKED (0x35)."""

        def reply(ctr, cmd, payload):
            return 0x35, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.unlock(b"\x00\x00\x00\x00")
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACCESS_LOCKED)
        finally:
            self._cleanup(master, slave)

    # ---- PROGRAM errors ----

    def test_program_access_locked(self):
        """PROGRAM: access locked (PGM not unlocked) -> 0x35."""

        def reply(ctr, cmd, payload):
            return 0x35, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.program(b"abcde")
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACCESS_LOCKED)
        finally:
            self._cleanup(master, slave)

    # ---- PROGRAM_6 errors ----

    def test_program6_access_locked(self):
        """PROGRAM_6: access locked -> 0x35."""

        def reply(ctr, cmd, payload):
            return 0x35, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.program6(b"abcdef")
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACCESS_LOCKED)
        finally:
            self._cleanup(master, slave)

    # ---- CLEAR_MEMORY errors ----

    def test_clear_memory_access_locked(self):
        """CLEAR_MEMORY: no PGM privilege -> ACCESS_LOCKED (0x35)."""

        def reply(ctr, cmd, payload):
            return 0x35, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.clear_memory(0x100)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACCESS_LOCKED)
        finally:
            self._cleanup(master, slave)

    # ---- BUILD_CHKSUM errors ----

    def test_build_chksum_parameter_out_of_range(self):
        """BUILD_CHKSUM: illegal address -> 0x32."""

        def reply(ctr, cmd, payload):
            return 0x32, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.build_chksum(0x100)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.PARAMETER_OUT_OF_RANGE)
        finally:
            self._cleanup(master, slave)

    # ---- Class C1: retryable errors ----

    def test_command_processor_busy(self):
        """C1: COMMAND_PROCESSOR_BUSY (0x10) — retryable."""

        def reply(ctr, cmd, payload):
            return 0x10, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.dnload(5, b"abcde")
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.COMMAND_PROCESSOR_BUSY)
        finally:
            self._cleanup(master, slave)

    def test_daq_processor_busy(self):
        """C1: DAQ_PROCESSOR_BUSY (0x11) — retryable."""

        def reply(ctr, cmd, payload):
            return 0x11, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.start_stop(1, 0, 1, 1, 100)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.DAQ_PROCESSOR_BUSY)
        finally:
            self._cleanup(master, slave)

    def test_internal_timeout(self):
        """C1: INTERNAL_TIMEOUT (0x12) — retryable."""

        def reply(ctr, cmd, payload):
            return 0x12, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.dnload(5, b"abcde")
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.INTERNAL_TIMEOUT)
        finally:
            self._cleanup(master, slave)

    # ---- Class C3: fatal errors ----

    def test_unknown_command(self):
        """C3: UNKNOWN_COMMAND (0x30)."""

        def reply(ctr, cmd, payload):
            return 0x30, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.dnload(5, b"abcde")
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.UNKNOWN_COMMAND)
        finally:
            self._cleanup(master, slave)

    def test_command_syntax(self):
        """C3: COMMAND_SYNTAX (0x31)."""

        def reply(ctr, cmd, payload):
            return 0x31, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.dnload(5, b"abcde")
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.COMMAND_SYNTAX)
        finally:
            self._cleanup(master, slave)

    def test_overload(self):
        """C3: OVERLOAD (0x34)."""

        def reply(ctr, cmd, payload):
            return 0x34, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.dnload(5, b"abcde")
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.OVERLOAD)
        finally:
            self._cleanup(master, slave)

    def test_resource_function_not_available(self):
        """C3: RESOURCE_FUNCTION_NOT_AVAILABLE (0x36)."""

        def reply(ctr, cmd, payload):
            return 0x36, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.get_ccp_version()
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.RESOURCE_FUNCTION_NOT_AVAILABLE)
        finally:
            self._cleanup(master, slave)

    # ---- Class C2: request errors ----

    def test_cold_start_request(self):
        """C2: COLD_START_REQUEST (0x20)."""

        def reply(ctr, cmd, payload):
            return 0x20, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.connect(STATION)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.COLD_START_REQUEST)
        finally:
            self._cleanup(master, slave)

    def test_cal_data_init_request(self):
        """C2: CAL_DATA_INIT_REQUEST (0x21)."""

        def reply(ctr, cmd, payload):
            return 0x21, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.dnload(5, b"abcde")
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.CAL_DATA_INIT_REQUEST)
        finally:
            self._cleanup(master, slave)

    def test_code_update_request(self):
        """C2: CODE_UPDATE_REQUEST (0x23)."""

        def reply(ctr, cmd, payload):
            return 0x23, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.program(b"abcde")
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.CODE_UPDATE_REQUEST)
        finally:
            self._cleanup(master, slave)

    def test_key_request(self):
        """C1: KEY_REQUEST (0x18) — embedded seed&key."""

        def reply(ctr, cmd, payload):
            return 0x18, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.dnload(5, b"abcde")
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.KEY_REQUEST)
        finally:
            self._cleanup(master, slave)

    def test_session_status_request(self):
        """C1: SESSION_STATUS_REQUEST (0x19) — embedded SET_S_STATUS."""

        def reply(ctr, cmd, payload):
            return 0x19, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.dnload(5, b"abcde")
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.SESSION_STATUS_REQUEST)
        finally:
            self._cleanup(master, slave)


if __name__ == "__main__":
    unittest.main()
