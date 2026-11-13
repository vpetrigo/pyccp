"""
Input validation tests — verifying that invalid parameters
raise errors before sending.
"""

import pytest


class TestValidation:
    """Tests that invalid input raises
    TypeError/ValueError without sending CRO frames.
    """

    def test_invalid_program6_length(self, master, slave):
        """program6 with wrong length must raise before sending."""
        for length in (0, 1, 5, 7, 8):
            with pytest.raises(ValueError):
                master.program6(bytes(length))
            assert len(slave.received) == 0

    def test_invalid_dnload_length(self, master, slave):
        """dnload with size mismatch must raise before sending."""
        with pytest.raises(ValueError):
            master.dnload(3, b"ab")
        with pytest.raises(ValueError):
            master.dnload(0, b"")
        with pytest.raises(ValueError):
            master.upload(0)

    def test_invalid_diag_service(self, master, slave):
        """diag_service with out-of-range service number must raise."""
        with pytest.raises(ValueError):
            master.diag_service(-1)
        with pytest.raises(ValueError):
            master.diag_service(65536)
        with pytest.raises(ValueError):
            master.diag_service(0, b"12345")
