"""Input validation tests — verifying that invalid parameters raise errors before sending."""

import unittest

from tests.virtual_bus import make_master_and_slave


class TestValidation(unittest.TestCase):
    """Tests that invalid input raises TypeError/ValueError without sending CRO frames."""

    def _cleanup(self, master, slave):
        """Stop slave thread and shut down both buses."""
        slave.stop()
        master.__exit__(None, None, None)

    def test_invalid_program6_length(self):
        """program6 with wrong length must raise before sending."""
        master, slave = make_master_and_slave()
        try:
            for length in (0, 1, 5, 7, 8):
                with self.assertRaises(ValueError):
                    master.program6(bytes(length))
                self.assertEqual(len(slave.received), 0)
        finally:
            self._cleanup(master, slave)

    def test_invalid_dnload_length(self):
        """dnload with size mismatch must raise before sending."""
        master, slave = make_master_and_slave()
        try:
            with self.assertRaises(ValueError):
                master.dnload(3, b"ab")
            with self.assertRaises(ValueError):
                master.dnload(0, b"")
            with self.assertRaises(ValueError):
                master.upload(0)
        finally:
            self._cleanup(master, slave)

    def test_invalid_diag_service(self):
        """diag_service with out-of-range service number must raise."""
        master, slave = make_master_and_slave()
        try:
            with self.assertRaises(ValueError):
                master.diag_service(-1)
            with self.assertRaises(ValueError):
                master.diag_service(65536)
            with self.assertRaises(ValueError):
                master.diag_service(0, b"12345")
        finally:
            self._cleanup(master, slave)


if __name__ == "__main__":
    unittest.main()
