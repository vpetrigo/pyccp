"""Example Sequence tests — CCP 2.1 Section 14 using virtual interface.

Covers all six Example Sequences:
- 14.1 Session log-in (unprotected + protected with UNLOCK)
- 14.2 Block DownLoad
- 14.3 Block UpLoad
- 14.4 Calibration Data Initialization
- 14.5 DAQ List Initialization
- 14.6 Code Update
"""

import pytest

from pyccp import ccp
from pyccp.ccp import ReturnCodes

STATION = 0x1234


class TestExampleSequences:
    """Tests for all six Example Sequences from CCP 2.1 Section 14."""

    def test_14_1_session_login_unprotected(self, master, slave):
        """14.1 Session log-in — no seed/key required.

        CONNECT -> GET_CCP_VERSION -> EXCHANGE_ID -> GET_SEED -> GET_S_STATUS
        -> SET_S_STATUS
        """

        def reply(ctr, cmd, payload):
            if cmd == ccp.GET_CCP_VERSION.code:
                return 0x00, bytes([2, 1])
            if cmd == ccp.EXCHANGE_ID.code:
                # capabilities: CAL|DAQ|PGM present, nothing protected
                return 0x00, bytes([0, 0, 0x43, 0x00])
            if cmd == ccp.GET_SEED.code:
                # resource=PGM(0x40), locked=0 (not protected)
                return 0x00, bytes([0, 0x12, 0x34, 0x56, 0x78])
            if cmd == ccp.GET_S_STATUS.code:
                return 0x00, bytes([0x81, 0x00])
            return 0x00, b""

        slave.reply = reply

        # CONNECT
        resp = master.connect(STATION)
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        # GET_CCP_VERSION
        resp = master.get_ccp_version()
        assert resp.code == ReturnCodes.ACKNOWLEDGE
        assert resp.data[:2] == bytes([2, 1])

        # EXCHANGE_ID
        resp = master.exchange_id(b"")
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        # GET_SEED (CAL resource)
        resp = master.get_seed(ccp.SecondaryResource.CAL)
        assert resp.code == ReturnCodes.ACKNOWLEDGE
        assert resp.data[0] == 0  # not locked

        # GET_S_STATUS
        resp = master.get_s_status()
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        # SET_S_STATUS (enable CAL)
        resp = master.set_s_status(0x81)
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        # Verify command sequence on slave side
        cmds = [m.data[0] for m in slave.received]
        assert ccp.CONNECT.code in cmds
        assert ccp.GET_CCP_VERSION.code in cmds
        assert ccp.EXCHANGE_ID.code in cmds
        assert ccp.GET_SEED.code in cmds
        assert ccp.GET_S_STATUS.code in cmds
        assert ccp.SET_S_STATUS.code in cmds

    def test_14_1_session_login_protected_with_unlock(self, master, slave):
        """14.1 Session log-in — seed/key required (UNLOCK step).

        CONNECT -> GET_CCP_VERSION -> EXCHANGE_ID -> GET_SEED -> UNLOCK
        -> GET_S_STATUS -> SET_S_STATUS
        """

        def reply(ctr, cmd, payload):
            if cmd == ccp.GET_CCP_VERSION.code:
                return 0x00, bytes([2, 1])
            if cmd == ccp.EXCHANGE_ID.code:
                # CAL is protected (bit 0 of byte 4)
                return 0x00, bytes([0, 0, 0x43, 0x01])
            if cmd == ccp.GET_SEED.code:
                # locked=1, seed follows
                return 0x00, bytes([1, 0x12, 0x34, 0x56, 0x78])
            if cmd == ccp.UNLOCK.code:
                # accept key
                return 0x00, bytes([0x43])  # privileges granted
            if cmd == ccp.GET_S_STATUS.code:
                return 0x00, bytes([0x81, 0x00])
            return 0x00, b""

        slave.reply = reply
        resp = master.connect(STATION)
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        resp = master.get_ccp_version()
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        resp = master.exchange_id(b"")
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        resp = master.get_seed(ccp.SecondaryResource.CAL)
        assert resp.code == ReturnCodes.ACKNOWLEDGE
        assert resp.data[0] == 1  # locked

        # UNLOCK with key
        resp = master.unlock(b"\xab\xcd\xef\x01")
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        resp = master.get_s_status()
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        resp = master.set_s_status(0x81)
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        cmds = [m.data[0] for m in slave.received]
        assert ccp.UNLOCK.code in cmds

    def test_14_2_block_download(self, master, slave):
        """14.2 Block DownLoad: CONNECT -> SET_MTA -> DNLOAD (n times)."""
        resp = master.connect(STATION)
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        resp = master.set_mta(0x1000)
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        data = bytes(range(10))
        for i in range(0, len(data), 5):
            chunk = data[i : i + 5]
            resp = master.dnload(len(chunk), chunk)
            assert resp.code == ReturnCodes.ACKNOWLEDGE

        cmds = [m.data[0] for m in slave.received]
        assert cmds[0] == ccp.CONNECT.code
        assert cmds[1] == ccp.SET_MTA.code
        assert cmds[2] == ccp.DNLOAD.code
        assert cmds[3] == ccp.DNLOAD.code

    def test_14_3_block_upload(self, master, slave):
        """14.3 Block UpLoad: CONNECT -> SET_MTA -> UPLOAD (n times)."""

        def reply(ctr, cmd, payload):
            if cmd == ccp.UPLOAD.code:
                size = payload[0]
                return 0x00, bytes(range(size))
            return 0x00, b""

        resp = master.connect(STATION)
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        resp = master.set_mta(0x2000)
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        for _ in range(2):
            resp = master.upload(5)
            assert resp.code == ReturnCodes.ACKNOWLEDGE
            assert len(resp.data) == 5

        cmds = [m.data[0] for m in slave.received]
        assert cmds[0] == ccp.CONNECT.code
        assert cmds[1] == ccp.SET_MTA.code
        assert cmds[2] == ccp.UPLOAD.code
        assert cmds[3] == ccp.UPLOAD.code

    def test_14_4_calibration_data_initialization(self, master, slave):
        """14.4 Calibration Data Initialization:

        CONNECT -> SET_S_STATUS(CAL=off) -> loop[SET_MTA, BUILD_CHKSUM,
        DNLOAD(if mismatch)] -> SELECT_CAL_PAGE -> SET_S_STATUS(CAL=on)
        """

        def reply(ctr, cmd, payload):
            if cmd == ccp.BUILD_CHKSUM.code:
                # Return a checksum that does NOT match -> trigger DNLOAD
                return 0x00, bytes([4, 0xFF, 0xFF, 0xFF, 0xFF])
            if cmd == ccp.GET_S_STATUS.code:
                return 0x00, bytes([0x81, 0x00])
            return 0x00, b""

        slave.reply = reply
        # CONNECT
        resp = master.connect(STATION)
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        # SET_S_STATUS(CAL=off)
        resp = master.set_s_status(0x80)
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        # SET_MTA
        resp = master.set_mta(0x1000)
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        # BUILD_CHKSUM
        resp = master.build_chksum(0x10)
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        # DNLOAD (checksum mismatch)
        resp = master.dnload(5, b"\x00\x01\x02\x03\x04")
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        # SELECT_CAL_PAGE
        resp = master.select_cal_page()
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        # SET_S_STATUS(CAL=on)
        resp = master.set_s_status(0x81)
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        cmds = [m.data[0] for m in slave.received]
        assert ccp.SET_S_STATUS.code in cmds
        assert ccp.SET_MTA.code in cmds
        assert ccp.BUILD_CHKSUM.code in cmds
        assert ccp.DNLOAD.code in cmds
        assert ccp.SELECT_CAL_PAGE.code in cmds

    def test_14_5_daq_list_initialization(self, master, slave):
        """14.5 DAQ List Initialization:

        CONNECT -> SET_S_STATUS(DAQ=0) -> GET_DAQ_SIZE ->
        loop[SET_DAQ_PTR, WRITE_DAQ] -> SET_S_STATUS(DAQ=1) -> START_STOP
        """

        def reply(ctr, cmd, payload):
            if cmd == ccp.GET_DAQ_SIZE.code:
                return 0x00, bytes([2, 0x20])  # 2 ODTs, 32 bytes
            if cmd == ccp.GET_S_STATUS.code:
                return 0x00, bytes([0x81, 0x00])
            return 0x00, b""

        # CONNECT
        resp = master.connect(STATION)
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        # SET_S_STATUS(DAQ=0)
        resp = master.set_s_status(0x80)
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        # GET_DAQ_SIZE
        resp = master.get_daq_size(0, 0x500)
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        # SET_DAQ_PTR + WRITE_DAQ (first entry)
        resp = master.set_daq_ptr(0, 0, 0)
        assert resp.code == ReturnCodes.ACKNOWLEDGE
        resp = master.write_daq(2, 0, 0x1000)
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        # SET_DAQ_PTR + WRITE_DAQ (second entry)
        resp = master.set_daq_ptr(0, 0, 1)
        assert resp.code == ReturnCodes.ACKNOWLEDGE
        resp = master.write_daq(4, 0, 0x2000)
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        # SET_S_STATUS(DAQ=1)
        resp = master.set_s_status(0x83)
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        # START_STOP
        resp = master.start_stop(1, 0, 0, 1, 100)
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        cmds = [m.data[0] for m in slave.received]
        assert ccp.SET_S_STATUS.code in cmds
        assert ccp.GET_DAQ_SIZE.code in cmds
        assert ccp.SET_DAQ_PTR.code in cmds
        assert ccp.WRITE_DAQ.code in cmds
        assert ccp.START_STOP.code in cmds

    def test_14_6_code_update(self, master, slave):
        """14.6 Code Update:

        CONNECT -> SET_MTA -> CLEAR_MEMORY ->
        loop[PROGRAM / PROGRAM6] -> PROGRAM(size=0) [finalize]
        """
        # CONNECT
        resp = master.connect(STATION)
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        # SET_MTA
        resp = master.set_mta(0x8000)
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        # CLEAR_MEMORY
        resp = master.clear_memory(0x100)
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        # PROGRAM (multiple chunks)
        resp = master.program(b"\x00\x01\x02\x03\x04")
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        resp = master.program6(b"\x05\x06\x07\x08\x09\x0a")
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        resp = master.program(b"\x0b\x0c")
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        # PROGRAM(size=0) — finalize
        resp = master.program(b"")
        assert resp.code == ReturnCodes.ACKNOWLEDGE

        cmds = [m.data[0] for m in slave.received]
        assert cmds[0] == ccp.CONNECT.code
        assert cmds[1] == ccp.SET_MTA.code
        assert cmds[2] == ccp.CLEAR_MEMORY.code
        assert ccp.PROGRAM.code in cmds
        assert ccp.PROGRAM_6.code in cmds
        # Last command must be PROGRAM (finalize)
        assert cmds[-1] == ccp.PROGRAM.code
        # Verify last PROGRAM has size=0
        last_msg = slave.received[-1]
        assert last_msg.data[2] == 0  # size byte = 0
