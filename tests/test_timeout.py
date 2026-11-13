"""Timeout tests — verifying behavior when no CRM response arrives."""

import time
import unittest

from tests.virtual_bus import STATION, make_master_and_slave


class TestTimeout(unittest.TestCase):
    """Tests for timeout behavior when the slave does not respond."""

    def test_timeout_returns_none(self):
        """No CRM reply within the command timeout -> None."""
        master, slave = make_master_and_slave()
        # Slave will ACK, but we stop it first so no reply arrives.
        slave.stop()
        # Use a short-timeout command (25 ms).
        start = time.monotonic()
        resp = master.connect(STATION)
        elapsed = time.monotonic() - start
        self.assertIsNone(resp)
        self.assertGreaterEqual(elapsed, 0.02)  # at least ~25 ms
        master.__exit__(None, None, None)


if __name__ == "__main__":
    unittest.main()
