"""Basic command tests — every mandatory and optional CCP command with an ACK reply."""

import pytest

from pyccp import ccp
from pyccp.ccp import ReturnCodes

STATION = 0x1234


class TestBasicCommands:
    """Core tests that use the python-can virtual interface for basic ACK replies."""

    def test_connect_ack(self, master, slave):
        resp = master.connect(STATION)
        assert resp is not None
        assert resp.code == ReturnCodes.ACKNOWLEDGE
        assert len(slave.received) == 1
        assert slave.received[0].data[0] == ccp.CONNECT.code

    def test_get_ccp_version_ack(self, master, slave):
        def reply(ctr, cmd, payload):
            return 0x00, bytes([2, 1])

        slave.reply = reply
        resp = master.get_ccp_version()
        assert resp is not None
        assert resp.code == ReturnCodes.ACKNOWLEDGE
        assert resp.data[:2] == bytes([2, 1])

    def test_exchange_id_ack(self, master, slave):
        def reply(ctr, cmd, payload):
            return 0x00, bytes([0, 0, 0x43, 0x00])  # capabilities

        slave.reply = reply
        resp = master.exchange_id(b"")
        assert resp is not None
        assert resp.code == ReturnCodes.ACKNOWLEDGE

    def test_set_mta_ack(self, master, slave):
        resp = master.set_mta(0x12345678)
        assert resp is not None
        assert resp.code == ReturnCodes.ACKNOWLEDGE

    def test_dnload_ack(self, master, slave):
        resp = master.dnload(5, b"abcde")
        assert resp is not None
        assert resp.code == ReturnCodes.ACKNOWLEDGE

    def test_upload_ack(self, master, slave):
        def reply(ctr, cmd, payload):
            size = payload[0]
            return 0x00, bytes(range(size))

        slave.reply = reply
        resp = master.upload(4)
        assert resp is not None
        assert resp.code == ReturnCodes.ACKNOWLEDGE
        assert resp.data[:4] == bytes([0, 1, 2, 3])

    def test_get_daq_size_ack(self, master, slave):
        def reply(ctr, cmd, payload):
            return 0x00, bytes([2, 0x20])  # 2 ODTs, 32 bytes capacity

        slave.reply = reply
        resp = master.get_daq_size(0, 0x500)
        assert resp is not None
        assert resp.code == ReturnCodes.ACKNOWLEDGE

    def test_set_daq_ptr_ack(self, master, slave):
        resp = master.set_daq_ptr(0, 0, 0)
        assert resp is not None
        assert resp.code == ReturnCodes.ACKNOWLEDGE

    def test_write_daq_ack(self, master, slave):
        resp = master.write_daq(2, 0, 0x1000)
        assert resp is not None
        assert resp.code == ReturnCodes.ACKNOWLEDGE

    def test_start_stop_ack(self, master, slave):
        resp = master.start_stop(1, 0, 1, 1, 100)
        assert resp is not None
        assert resp.code == ReturnCodes.ACKNOWLEDGE

    def test_disconnect_ack(self, master, slave):
        resp = master.disconnect(ccp.DisconnectType.PERMANENT, STATION)
        assert resp is not None
        assert resp.code == ReturnCodes.ACKNOWLEDGE

    def test_dnload6_ack(self, master, slave):
        resp = master.dnload6(b"abcdef")
        assert resp is not None
        assert resp.code == ReturnCodes.ACKNOWLEDGE

    def test_short_up_ack(self, master, slave):
        def reply(ctr, cmd, payload):
            size = payload[0]
            return 0x00, bytes(range(size))

        slave.reply = reply
        resp = master.short_up(4, 0x1000)
        assert resp is not None
        assert resp.code == ReturnCodes.ACKNOWLEDGE

    def test_start_stop_all_ack(self, master, slave):
        resp = master.start_stop_all(1)
        assert resp is not None
        assert resp.code == ReturnCodes.ACKNOWLEDGE

    def test_set_s_status_ack(self, master, slave):
        resp = master.set_s_status(0x81)
        assert resp is not None
        assert resp.code == ReturnCodes.ACKNOWLEDGE

    def test_get_s_status_ack(self, master, slave):
        def reply(ctr, cmd, payload):
            return 0x00, bytes([0x81, 0x00])

        slave.reply = reply
        resp = master.get_s_status()
        assert resp is not None
        assert resp.code == ReturnCodes.ACKNOWLEDGE
        assert resp.data[0] == 0x81

    def test_build_chksum_ack(self, master, slave):
        def reply(ctr, cmd, payload):
            return 0x00, bytes([4, 0xAA, 0xBB, 0xCC, 0xDD])

        slave.reply = reply
        resp = master.build_chksum(0x100)
        assert resp is not None
        assert resp.code == ReturnCodes.ACKNOWLEDGE

    def test_clear_memory_ack(self, master, slave):
        resp = master.clear_memory(0x100)
        assert resp is not None
        assert resp.code == ReturnCodes.ACKNOWLEDGE

    def test_program_ack(self, master, slave):
        resp = master.program(b"abcde")
        assert resp is not None
        assert resp.code == ReturnCodes.ACKNOWLEDGE

    def test_program_empty_ack(self, master, slave):
        resp = master.program(b"")
        assert resp is not None
        assert resp.code == ReturnCodes.ACKNOWLEDGE

    def test_program6_ack(self, master, slave):
        resp = master.program6(b"\x00\x01\x02\x03\x04\x05")
        assert resp is not None
        assert resp.code == ReturnCodes.ACKNOWLEDGE

    def test_diag_service_ack(self, master, slave):
        resp = master.diag_service(0x1234)
        assert resp is not None
        assert resp.code == ReturnCodes.ACKNOWLEDGE

    def test_get_active_cal_page_ack(self, master, slave):
        resp = master.get_active_cal_page()
        assert resp is not None
        assert resp.code == ReturnCodes.ACKNOWLEDGE

    def test_select_cal_page_ack(self, master, slave):
        resp = master.select_cal_page()
        assert resp is not None
        assert resp.code == ReturnCodes.ACKNOWLEDGE

    def test_unlock_ack(self, master, slave):
        resp = master.unlock(b"\x01\x02\x03\x04")
        assert resp is not None
        assert resp.code == ReturnCodes.ACKNOWLEDGE

    def test_get_seed_ack(self, master, slave):
        def reply(ctr, cmd, payload):
            return 0x00, bytes([1, 0x12, 0x34, 0x56, 0x78])

        slave.reply = reply
        resp = master.get_seed(ccp.SecondaryResource.PGM)
        assert resp is not None
        assert resp.code == ReturnCodes.ACKNOWLEDGE

    def test_move_ack(self, master, slave):
        resp = master.move(0x100)
        assert resp is not None
        assert resp.code == ReturnCodes.ACKNOWLEDGE

    def test_test_ack(self, master, slave):
        resp = master.test(STATION)
        assert resp is not None
        assert resp.code == ReturnCodes.ACKNOWLEDGE
