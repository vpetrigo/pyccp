"""Fail-scenario tests — CCP 2.1 error-code matrix (Section 16.1).

Tests that the Master correctly receives and reports non-ACK return codes
from the slave for various commands.
"""

from pyccp import ccp
from pyccp.ccp import ReturnCodes

STATION = 0x1234


class TestErrorCodes:
    """Tests for error return codes from the CCP 2.1 error-code matrix."""

    # ---- CONNECT errors ----

    def test_connect_access_denied(self, master, slave):
        """CONNECT: session currently not possible -> ACCESS_DENIED (0x33)."""

        def reply(ctr, cmd, payload):
            return 0x33, b""

        slave.reply = reply
        resp = master.connect(STATION)
        assert resp is not None
        assert resp.code == ReturnCodes.ACCESS_DENIED

    def test_connect_parameter_out_of_range(self, master, slave):
        """CONNECT: invalid station address -> PARAMETER_OUT_OF_RANGE (0x32)."""

        def reply(ctr, cmd, payload):
            return 0x32, b""

        slave.reply = reply
        resp = master.connect(STATION)
        assert resp is not None
        assert resp.code == ReturnCodes.PARAMETER_OUT_OF_RANGE

    # ---- SET_MTA errors ----

    def test_set_mta_parameter_out_of_range(self, master, slave):
        """SET_MTA: illegal MTA#, base address, address ext -> 0x32."""

        def reply(ctr, cmd, payload):
            return 0x32, b""

        slave.reply = reply
        resp = master.set_mta(0xFFFFFFFF)
        assert resp is not None
        assert resp.code == ReturnCodes.PARAMETER_OUT_OF_RANGE

    # ---- DNLOAD errors ----

    def test_dnload_access_denied(self, master, slave):
        """DNLOAD: write attempt to ROM -> ACCESS_DENIED (0x33)."""

        def reply(ctr, cmd, payload):
            return 0x33, b""

        slave.reply = reply
        resp = master.dnload(5, b"abcde")
        assert resp is not None
        assert resp.code == ReturnCodes.ACCESS_DENIED

    def test_dnload_parameter_out_of_range(self, master, slave):
        """DNLOAD: data block size > 5 -> PARAMETER_OUT_OF_RANGE (0x32)."""

        def reply(ctr, cmd, payload):
            return 0x32, b""

        slave.reply = reply
        resp = master.dnload(5, b"abcde")
        assert resp is not None
        assert resp.code == ReturnCodes.PARAMETER_OUT_OF_RANGE

    def test_dnload_access_locked(self, master, slave):
        """DNLOAD: access locked (CAL not unlocked) -> 0x35."""

        def reply(ctr, cmd, payload):
            return 0x35, b""

        slave.reply = reply
        resp = master.dnload(5, b"abcde")
        assert resp is not None
        assert resp.code == ReturnCodes.ACCESS_LOCKED

    # ---- UPLOAD errors ----

    def test_upload_access_denied(self, master, slave):
        """UPLOAD: read attempt to protected area -> ACCESS_DENIED (0x33)."""

        def reply(ctr, cmd, payload):
            return 0x33, b""

        slave.reply = reply
        resp = master.upload(4)
        assert resp is not None
        assert resp.code == ReturnCodes.ACCESS_DENIED

    def test_upload_parameter_out_of_range(self, master, slave):
        """UPLOAD: block size > 5 -> PARAMETER_OUT_OF_RANGE (0x32)."""

        def reply(ctr, cmd, payload):
            return 0x32, b""

        slave.reply = reply
        resp = master.upload(4)
        assert resp is not None
        assert resp.code == ReturnCodes.PARAMETER_OUT_OF_RANGE

    # ---- GET_DAQ_SIZE errors ----

    def test_get_daq_size_parameter_out_of_range(self, master, slave):
        """GET_DAQ_SIZE: invalid DAQ list handle -> 0x32."""

        def reply(ctr, cmd, payload):
            return 0x32, b""

        slave.reply = reply
        resp = master.get_daq_size(0, 0x500)
        assert resp is not None
        assert resp.code == ReturnCodes.PARAMETER_OUT_OF_RANGE

    # ---- SET_DAQ_PTR errors ----

    def test_set_daq_ptr_parameter_out_of_range(self, master, slave):
        """SET_DAQ_PTR: invalid ODT/ODTE index -> 0x32."""

        def reply(ctr, cmd, payload):
            return 0x32, b""

        slave.reply = reply
        resp = master.set_daq_ptr(0, 0, 0)
        assert resp is not None
        assert resp.code == ReturnCodes.PARAMETER_OUT_OF_RANGE

    # ---- WRITE_DAQ errors ----

    def test_write_daq_parameter_out_of_range(self, master, slave):
        """WRITE_DAQ: invalid attribute/address -> 0x32."""

        def reply(ctr, cmd, payload):
            return 0x32, b""

        slave.reply = reply
        resp = master.write_daq(2, 0, 0x1000)
        assert resp is not None
        assert resp.code == ReturnCodes.PARAMETER_OUT_OF_RANGE

    # ---- START_STOP errors ----

    def test_start_stop_parameter_out_of_range(self, master, slave):
        """START_STOP: invalid DAQ list handle -> 0x32."""

        def reply(ctr, cmd, payload):
            return 0x32, b""

        slave.reply = reply
        resp = master.start_stop(1, 0, 1, 1, 100)
        assert resp is not None
        assert resp.code == ReturnCodes.PARAMETER_OUT_OF_RANGE

    def test_start_stop_access_denied(self, master, slave):
        """START_STOP: DAQ not allowed -> 0x33."""

        def reply(ctr, cmd, payload):
            return 0x33, b""

        slave.reply = reply
        resp = master.start_stop(1, 0, 1, 1, 100)
        assert resp is not None
        assert resp.code == ReturnCodes.ACCESS_DENIED

    # ---- DISCONNECT errors ----

    def test_disconnect_parameter_out_of_range(self, master, slave):
        """DISCONNECT: invalid station address -> 0x32."""

        def reply(ctr, cmd, payload):
            return 0x32, b""

        slave.reply = reply
        resp = master.disconnect(ccp.DisconnectType.PERMANENT, STATION)
        assert resp is not None
        assert resp.code == ReturnCodes.PARAMETER_OUT_OF_RANGE

    # ---- DNLOAD6 errors ----

    def test_dnload6_access_denied(self, master, slave):
        """DNLOAD6: write to ROM -> 0x33."""

        def reply(ctr, cmd, payload):
            return 0x33, b""

        slave.reply = reply
        resp = master.dnload6(b"abcdef")
        assert resp is not None
        assert resp.code == ReturnCodes.ACCESS_DENIED

    # ---- SHORT_UP errors ----

    def test_short_up_access_denied(self, master, slave):
        """SHORT_UP: read from protected area -> 0x33."""

        def reply(ctr, cmd, payload):
            return 0x33, b""

        slave.reply = reply
        resp = master.short_up(4, 0x1000)
        assert resp is not None
        assert resp.code == ReturnCodes.ACCESS_DENIED

    def test_short_up_parameter_out_of_range(self, master, slave):
        """SHORT_UP: invalid size/address -> 0x32."""

        def reply(ctr, cmd, payload):
            return 0x32, b""

        slave.reply = reply
        resp = master.short_up(4, 0x1000)
        assert resp is not None
        assert resp.code == ReturnCodes.PARAMETER_OUT_OF_RANGE

    # ---- START_STOP_ALL errors ----

    def test_start_stop_all_parameter_out_of_range(self, master, slave):
        """START_STOP_ALL: invalid mode -> 0x32."""

        def reply(ctr, cmd, payload):
            return 0x32, b""

        slave.reply = reply
        resp = master.start_stop_all(1)
        assert resp is not None
        assert resp.code == ReturnCodes.PARAMETER_OUT_OF_RANGE

    # ---- SET_S_STATUS errors ----

    def test_set_s_status_parameter_out_of_range(self, master, slave):
        """SET_S_STATUS: invalid status byte -> 0x32."""

        def reply(ctr, cmd, payload):
            return 0x32, b""

        slave.reply = reply
        resp = master.set_s_status(0x81)
        assert resp is not None
        assert resp.code == ReturnCodes.PARAMETER_OUT_OF_RANGE

    # ---- BUILD_CHKSUM errors ----

    def test_build_chksum_parameter_out_of_range(self, master, slave):
        """BUILD_CHKSUM: invalid MTA -> 0x32."""

        def reply(ctr, cmd, payload):
            return 0x32, b""

        slave.reply = reply
        resp = master.build_chksum(0x100)
        assert resp is not None
        assert resp.code == ReturnCodes.PARAMETER_OUT_OF_RANGE

    # ---- CLEAR_MEMORY errors ----

    def test_clear_memory_parameter_out_of_range(self, master, slave):
        """CLEAR_MEMORY: invalid MTA -> 0x32."""

        def reply(ctr, cmd, payload):
            return 0x32, b""

        slave.reply = reply
        resp = master.clear_memory(0x100)
        assert resp is not None
        assert resp.code == ReturnCodes.PARAMETER_OUT_OF_RANGE

    # ---- PROGRAM errors ----

    def test_program_access_denied(self, master, slave):
        """PROGRAM: write to non-flash area -> 0x33."""

        def reply(ctr, cmd, payload):
            return 0x33, b""

        slave.reply = reply
        resp = master.program(b"abcde")
        assert resp is not None
        assert resp.code == ReturnCodes.ACCESS_DENIED

    def test_program_parameter_out_of_range(self, master, slave):
        """PROGRAM: invalid data -> 0x32."""

        def reply(ctr, cmd, payload):
            return 0x32, b""

        slave.reply = reply
        resp = master.program(b"abcde")
        assert resp is not None
        assert resp.code == ReturnCodes.PARAMETER_OUT_OF_RANGE

    # ---- PROGRAM6 errors ----

    def test_program6_access_denied(self, master, slave):
        """PROGRAM6: write to non-flash area -> 0x33."""

        def reply(ctr, cmd, payload):
            return 0x33, b""

        slave.reply = reply
        resp = master.program6(b"\x00\x01\x02\x03\x04\x05")
        assert resp is not None
        assert resp.code == ReturnCodes.ACCESS_DENIED

    def test_program6_parameter_out_of_range(self, master, slave):
        """PROGRAM6: invalid data -> 0x32."""

        def reply(ctr, cmd, payload):
            return 0x32, b""

        slave.reply = reply
        resp = master.program6(b"\x00\x01\x02\x03\x04\x05")
        assert resp is not None
        assert resp.code == ReturnCodes.PARAMETER_OUT_OF_RANGE

    # ---- DIAG_SERVICE errors ----

    def test_diag_service_access_denied(self, master, slave):
        """DIAG_SERVICE: service not available -> 0x33."""

        def reply(ctr, cmd, payload):
            return 0x33, b""

        slave.reply = reply
        resp = master.diag_service(0x1234)
        assert resp is not None
        assert resp.code == ReturnCodes.ACCESS_DENIED

    # ---- GET_SEED errors ----

    def test_get_seed_parameter_out_of_range(self, master, slave):
        """GET_SEED: invalid resource -> 0x32."""

        def reply(ctr, cmd, payload):
            return 0x32, b""

        slave.reply = reply
        resp = master.get_seed(ccp.SecondaryResource.PGM)
        assert resp is not None
        assert resp.code == ReturnCodes.PARAMETER_OUT_OF_RANGE

    # ---- UNLOCK errors ----

    def test_unlock_access_locked(self, master, slave):
        """UNLOCK: bad key -> ACCESS_LOCKED (0x35)."""

        def reply(ctr, cmd, payload):
            return 0x35, b""

        slave.reply = reply
        resp = master.unlock(b"\x01\x02\x03\x04")
        assert resp is not None
        assert resp.code == ReturnCodes.ACCESS_LOCKED

    # ---- MOVE errors ----

    def test_move_parameter_out_of_range(self, master, slave):
        """MOVE: invalid size -> 0x32."""

        def reply(ctr, cmd, payload):
            return 0x32, b""

        slave.reply = reply
        resp = master.move(0x100)
        assert resp is not None
        assert resp.code == ReturnCodes.PARAMETER_OUT_OF_RANGE

    # ---- TEST errors ----

    def test_test_parameter_out_of_range(self, master, slave):
        """TEST: invalid station -> 0x32."""

        def reply(ctr, cmd, payload):
            return 0x32, b""

        slave.reply = reply
        resp = master.test(STATION)
        assert resp is not None
        assert resp.code == ReturnCodes.PARAMETER_OUT_OF_RANGE
