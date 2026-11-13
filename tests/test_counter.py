"""Counter tests — verifying CTR byte increments correctly."""

import pytest

STATION = 0x1234


class TestCounter:
    """Tests for the CCP counter (CTR) byte behavior."""

    def test_counter_increments_on_each_command(self, master, slave):
        """CTR byte must advance after every successful send_cro."""
        initial = master.ctr.value
        master.connect(STATION)
        assert master.ctr.value == (initial + 1) % 256
        master.set_mta(0x1000)
        assert master.ctr.value == (initial + 2) % 256
