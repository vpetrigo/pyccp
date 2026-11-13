"""Basic command tests — every mandatory and optional CCP command with an ACK reply."""

import unittest

from pyccp import ccp
from pyccp.ccp import ReturnCodes
from tests.virtual_bus import STATION, make_master_and_slave


class TestBasicCommands(unittest.TestCase):
    """Core tests that use the python-can virtual interface for basic ACK replies."""

    def _cleanup(self, master, slave):
        """Stop slave thread and shut down both buses."""
        slave.stop()
        master.__exit__(None, None, None)

    def test_connect_ack(self):
        master, slave = make_master_and_slave()
        try:
            resp = master.connect(STATION)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
            self.assertEqual(len(slave.received), 1)
            self.assertEqual(slave.received[0].data[0], ccp.CONNECT.code)
        finally:
            self._cleanup(master, slave)

    def test_get_ccp_version_ack(self):
        def reply(ctr, cmd, payload):
            return 0x00, bytes([2, 1])

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.get_ccp_version()
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
            self.assertEqual(resp.data[:2], bytes([2, 1]))
        finally:
            self._cleanup(master, slave)

    def test_exchange_id_ack(self):
        def reply(ctr, cmd, payload):
            return 0x00, bytes([0, 0, 0x43, 0x00])  # capabilities

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.exchange_id(b"")
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
        finally:
            self._cleanup(master, slave)

    def test_set_mta_ack(self):
        master, slave = make_master_and_slave()
        try:
            resp = master.set_mta(0x12345678)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
        finally:
            self._cleanup(master, slave)

    def test_dnload_ack(self):
        master, slave = make_master_and_slave()
        try:
            resp = master.dnload(5, b"abcde")
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
        finally:
            self._cleanup(master, slave)

    def test_upload_ack(self):
        def reply(ctr, cmd, payload):
            size = payload[0]
            return 0x00, bytes(range(size))

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.upload(4)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
            self.assertEqual(resp.data[:4], bytes([0, 1, 2, 3]))
        finally:
            self._cleanup(master, slave)

    def test_get_daq_size_ack(self):
        def reply(ctr, cmd, payload):
            return 0x00, bytes([2, 0x20])  # 2 ODTs, 32 bytes capacity

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.get_daq_size(0, 0x500)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
        finally:
            self._cleanup(master, slave)

    def test_set_daq_ptr_ack(self):
        master, slave = make_master_and_slave()
        try:
            resp = master.set_daq_ptr(0, 0, 0)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
        finally:
            self._cleanup(master, slave)

    def test_write_daq_ack(self):
        master, slave = make_master_and_slave()
        try:
            resp = master.write_daq(2, 0, 0x1000)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
        finally:
            self._cleanup(master, slave)

    def test_start_stop_ack(self):
        master, slave = make_master_and_slave()
        try:
            resp = master.start_stop(1, 0, 1, 1, 100)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
        finally:
            self._cleanup(master, slave)

    def test_disconnect_ack(self):
        master, slave = make_master_and_slave()
        try:
            resp = master.disconnect(ccp.DisconnectType.PERMANENT, STATION)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
        finally:
            self._cleanup(master, slave)

    def test_dnload6_ack(self):
        master, slave = make_master_and_slave()
        try:
            resp = master.dnload6(b"abcdef")
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
        finally:
            self._cleanup(master, slave)

    def test_short_up_ack(self):
        def reply(ctr, cmd, payload):
            size = payload[0]
            return 0x00, bytes(range(size))

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.short_up(4, 0x1000)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
        finally:
            self._cleanup(master, slave)

    def test_start_stop_all_ack(self):
        master, slave = make_master_and_slave()
        try:
            resp = master.start_stop_all(1)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
        finally:
            self._cleanup(master, slave)

    def test_set_s_status_ack(self):
        master, slave = make_master_and_slave()
        try:
            resp = master.set_s_status(0x81)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
        finally:
            self._cleanup(master, slave)

    def test_get_s_status_ack(self):
        def reply(ctr, cmd, payload):
            return 0x00, bytes([0x81, 0x00])

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.get_s_status()
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
            self.assertEqual(resp.data[0], 0x81)
        finally:
            self._cleanup(master, slave)

    def test_build_chksum_ack(self):
        def reply(ctr, cmd, payload):
            return 0x00, bytes([4, 0xAA, 0xBB, 0xCC, 0xDD])

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.build_chksum(0x100)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
        finally:
            self._cleanup(master, slave)

    def test_clear_memory_ack(self):
        master, slave = make_master_and_slave()
        try:
            resp = master.clear_memory(0x100)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
        finally:
            self._cleanup(master, slave)

    def test_program_ack(self):
        master, slave = make_master_and_slave()
        try:
            resp = master.program(b"abcde")
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
        finally:
            self._cleanup(master, slave)

    def test_program_empty_ack(self):
        master, slave = make_master_and_slave()
        try:
            resp = master.program(b"")
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
        finally:
            self._cleanup(master, slave)

    def test_program6_ack(self):
        master, slave = make_master_and_slave()
        try:
            resp = master.program6(b"\x00\x01\x02\x03\x04\x05")
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
        finally:
            self._cleanup(master, slave)

    def test_diag_service_ack(self):
        master, slave = make_master_and_slave()
        try:
            resp = master.diag_service(0x1234)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
        finally:
            self._cleanup(master, slave)

    def test_get_active_cal_page_ack(self):
        master, slave = make_master_and_slave()
        try:
            resp = master.get_active_cal_page()
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
        finally:
            self._cleanup(master, slave)

    def test_select_cal_page_ack(self):
        master, slave = make_master_and_slave()
        try:
            resp = master.select_cal_page()
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
        finally:
            self._cleanup(master, slave)

    def test_unlock_ack(self):
        master, slave = make_master_and_slave()
        try:
            resp = master.unlock(b"\x01\x02\x03\x04")
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
        finally:
            self._cleanup(master, slave)

    def test_get_seed_ack(self):
        def reply(ctr, cmd, payload):
            return 0x00, bytes([1, 0x12, 0x34, 0x56, 0x78])

        master, slave = make_master_and_slave(reply)
        try:
            resp = master.get_seed(ccp.SecondaryResource.PGM)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
        finally:
            self._cleanup(master, slave)

    def test_move_ack(self):
        master, slave = make_master_and_slave()
        try:
            resp = master.move(0x100)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
        finally:
            self._cleanup(master, slave)

    def test_test_ack(self):
        master, slave = make_master_and_slave()
        try:
            resp = master.test(STATION)
            self.assertIsNotNone(resp)
            self.assertEqual(resp.code, ReturnCodes.ACKNOWLEDGE)
        finally:
            self._cleanup(master, slave)


if __name__ == "__main__":
    unittest.main()
