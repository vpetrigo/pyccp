"""Timeout tests — verifying behavior when no CRM response arrives."""

import time

from pyccp.ccp import CONNECT

STATION = 0x1234


class TestTimeout:
    """Tests for timeout behavior when the slave does not respond."""

    def test_timeout_returns_none(self, master, slave):
        """No CRM reply within the command timeout -> None."""
        # Slave will ACK, but we stop it first so no reply arrives.
        slave.stop()
        # Use a short-timeout command (25 ms).
        start = time.perf_counter()
        resp = master.connect(STATION)
        elapsed = time.perf_counter() - start
        assert resp is None
        assert elapsed >= CONNECT.timeout / 1000.0  # at least ~25 ms
