"""Counter tests — verifying CTR byte increments correctly."""

import unittest

from tests.virtual_bus import STATION, make_master_and_slave


class TestCounter(unittest.TestCase):
    """Tests for the CCP counter (CTR) byte behavior."""

    def _cleanup(self, master, slave):
        """Stop slave thread and shut down both buses."""
        slave.stop()
        master.__exit__(None, None, None)

    def test_counter_increments_on_each_command(self):
        """CTR byte must advance after every successful send_cro."""
        master, slave = make_master_and_slave()
        try:
            initial = master.ctr.value
            master.connect(STATION)
            self.assertEqual(master.ctr.value, (initial + 1) % 256)
            master.set_mta(0x1000)
            self.assertEqual(master.ctr.value, (initial + 2) % 256)
        finally:
            self._cleanup(master, slave)


if __name__ == "__main__":
    unittest.main()
