"""Example Sequence tests — CCP 2.1 Section 14 using virtual interface.

Covers all six Example Sequences:
- 14.1 Session log-in (unprotected + protected with UNLOCK)
- 14.2 Block DownLoad
- 14.3 Block UpLoad
- 14.4 Calibration Data Initialization
- 14.5 DAQ List Initialization
- 14.6 Code Update
"""

import unittest

from pyccp import ccp
from pyccp.ccp import ReturnCodes
from tests.virtual_bus import STATION, make_master_and_slave


class TestExampleSequences(unittest.TestCase):
    """Tests for all six Example Sequences from CCP 2.1 Section 14."""

    def _ack_slave(self):
        """Return a reply_fn that always ACKs."""
        return None

    def _cleanup(self, master, slave):
        """Stop slave thread and shut down both buses."""
        slave.stop()
        master.__exit__(None, None, None)

    def test_14_1_session_login_unprotected(self):
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

        master, slave = make_master_and_slave(reply)
        try:
            # CONNECT
            resp = master.connect(STATION)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            # GET_CCP_VERSION
            resp = master.get_ccp_version()
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
            self.assertEqual(resp.data[:2], bytes([2, 1]))

            # EXCHANGE_ID
            resp = master.exchange_id(b"")
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            # GET_SEED (CAL resource)
            resp = master.get_seed(ccp.SecondaryResource.CAL)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
            self.assertEqual(resp.data[0], 0)  # not locked

            # GET_S_STATUS
            resp = master.get_s_status()
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            # SET_S_STATUS (enable CAL)
            resp = master.set_s_status(0x81)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            # Verify command sequence on slave side
            cmds = [m.data[0] for m in slave.received]
            self.assertIn(ccp.CONNECT.code, cmds)
            self.assertIn(ccp.GET_CCP_VERSION.code, cmds)
            self.assertIn(ccp.EXCHANGE_ID.code, cmds)
            self.assertIn(ccp.GET_SEED.code, cmds)
            self.assertIn(ccp.GET_S_STATUS.code, cmds)
            self.assertIn(ccp.SET_S_STATUS.code, cmds)
        finally:
            self._cleanup(master, slave)

    def test_14_1_session_login_protected_with_unlock(self):
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

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.connect(STATION)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            resp = master.get_ccp_version()
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            resp = master.exchange_id(b"")
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            resp = master.get_seed(ccp.SecondaryResource.CAL)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
            self.assertEqual(resp.data[0], 1)  # locked

            # UNLOCK with key
            resp = master.unlock(b"\xab\xcd\xef\x01")
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            resp = master.get_s_status()
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            resp = master.set_s_status(0x81)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            cmds = [m.data[0] for m in slave.received]
            self.assertIn(ccp.UNLOCK.code, cmds)
        finally:
            self._cleanup(master, slave)

    def test_14_2_block_download(self):
        """14.2 Block DownLoad: CONNECT -> SET_MTA -> DNLOAD (n times)."""
        master, slave = make_master_and_slave()
        try:
            resp = master.connect(STATION)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            resp = master.set_mta(0x1000)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            data = bytes(range(10))
            for i in range(0, len(data), 5):
                chunk = data[i : i + 5]
                resp = master.dnload(len(chunk), chunk)
                self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            cmds = [m.data[0] for m in slave.received]
            self.assertEqual(cmds[0], ccp.CONNECT.code)
            self.assertEqual(cmds[1], ccp.SET_MTA.code)
            self.assertEqual(cmds[2], ccp.DNLOAD.code)
            self.assertEqual(cmds[3], ccp.DNLOAD.code)
        finally:
            self._cleanup(master, slave)

    def test_14_3_block_upload(self):
        """14.3 Block UpLoad: CONNECT -> SET_MTA -> UPLOAD (n times)."""

        def reply(ctr, cmd, payload):
            if cmd == ccp.UPLOAD.code:
                size = payload[0]
                return 0x00, bytes(range(size))
            return 0x00, b""

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.connect(STATION)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            resp = master.set_mta(0x2000)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            for _ in range(2):
                resp = master.upload(5)
                self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
                self.assertEqual(len(resp.data), 5)

            cmds = [m.data[0] for m in slave.received]
            self.assertEqual(cmds[0], ccp.CONNECT.code)
            self.assertEqual(cmds[1], ccp.SET_MTA.code)
            self.assertEqual(cmds[2], ccp.UPLOAD.code)
            self.assertEqual(cmds[3], ccp.UPLOAD.code)
        finally:
            self._cleanup(master, slave)

    def test_14_4_calibration_data_initialization(self):
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

        master, slave = make_master_and_slave(reply)
        try:
            # CONNECT
            resp = master.connect(STATION)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            # SET_S_STATUS(CAL=off)
            resp = master.set_s_status(0x80)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            # SET_MTA
            resp = master.set_mta(0x1000)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            # BUILD_CHKSUM
            resp = master.build_chksum(0x10)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            # DNLOAD (checksum mismatch)
            resp = master.dnload(5, b"\x00\x01\x02\x03\x04")
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            # SELECT_CAL_PAGE
            resp = master.select_cal_page()
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            # SET_S_STATUS(CAL=on)
            resp = master.set_s_status(0x81)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            cmds = [m.data[0] for m in slave.received]
            self.assertIn(ccp.SET_S_STATUS.code, cmds)
            self.assertIn(ccp.SET_MTA.code, cmds)
            self.assertIn(ccp.BUILD_CHKSUM.code, cmds)
            self.assertIn(ccp.DNLOAD.code, cmds)
            self.assertIn(ccp.SELECT_CAL_PAGE.code, cmds)
        finally:
            self._cleanup(master, slave)

    def test_14_5_daq_list_initialization(self):
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

        master, slave = make_master_and_slave(reply)
        try:
            # CONNECT
            resp = master.connect(STATION)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            # SET_S_STATUS(DAQ=0)
            resp = master.set_s_status(0x80)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            # GET_DAQ_SIZE
            resp = master.get_daq_size(0, 0x500)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            # SET_DAQ_PTR + WRITE_DAQ (first entry)
            resp = master.set_daq_ptr(0, 0, 0)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
            resp = master.write_daq(2, 0, 0x1000)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            # SET_DAQ_PTR + WRITE_DAQ (second entry)
            resp = master.set_daq_ptr(0, 0, 1)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
            resp = master.write_daq(4, 0, 0x2000)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            # SET_S_STATUS(DAQ=1)
            resp = master.set_s_status(0x83)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            # START_STOP
            resp = master.start_stop(1, 0, 0, 1, 100)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            cmds = [m.data[0] for m in slave.received]
            self.assertIn(ccp.SET_S_STATUS.code, cmds)
            self.assertIn(ccp.GET_DAQ_SIZE.code, cmds)
            self.assertIn(ccp.SET_DAQ_PTR.code, cmds)
            self.assertIn(ccp.WRITE_DAQ.code, cmds)
            self.assertIn(ccp.START_STOP.code, cmds)
        finally:
            self._cleanup(master, slave)

    def test_14_6_code_update(self):
        """14.6 Code Update:

        CONNECT -> SET_MTA -> CLEAR_MEMORY ->
        loop[PROGRAM / PROGRAM6] -> PROGRAM(size=0) [finalize]
        """
        master, slave = make_master_and_slave()
        try:
            # CONNECT
            resp = master.connect(STATION)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            # SET_MTA
            resp = master.set_mta(0x8000)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            # CLEAR_MEMORY
            resp = master.clear_memory(0x100)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            # PROGRAM (multiple chunks)
            resp = master.program(b"\x00\x01\x02\x03\x04")
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            resp = master.program6(b"\x05\x06\x07\x08\x09\x0a")
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            resp = master.program(b"\x0b\x0c")
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            # PROGRAM(size=0) — finalize
            resp = master.program(b"")
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)

            cmds = [m.data[0] for m in slave.received]
            self.assertEqual(cmds[0], ccp.CONNECT.code)
            self.assertEqual(cmds[1], ccp.SET_MTA.code)
            self.assertEqual(cmds[2], ccp.CLEAR_MEMORY.code)
            self.assertIn(ccp.PROGRAM.code, cmds)
            self.assertIn(ccp.PROGRAM_6.code, cmds)
            # Last command must be PROGRAM (finalize)
            self.assertEqual(cmds[-1], ccp.PROGRAM.code)
            # Verify last PROGRAM has size=0
            last_msg = slave.received[-1]
            self.assertEqual(last_msg.data[2], 0)  # size byte = 0
        finally:
            self._cleanup(master, slave)


if __name__ == "__main__":
    unittest.main()
