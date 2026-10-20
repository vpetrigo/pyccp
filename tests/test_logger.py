import logging
import unittest

from pyccp.logger import Logger


class TestLogger(unittest.TestCase):
    def test_instances_do_not_share_identity_or_error_history(self):
        master = Logger("pyccp.master")
        master.error("master failure")
        slave = Logger("pyccp.slave")
        slave.warn("slave warning")
        self.assertIsNot(master, slave)
        self.assertEqual(master.logger.name, "pyccp.master")
        self.assertEqual(slave.logger.name, "pyccp.slave")
        self.assertEqual(master.get_last_error(), (logging.ERROR, "master failure"))
        self.assertEqual(master.get_last_error(), (None, None))
        self.assertEqual(slave.get_last_error(), (logging.WARNING, "slave warning"))

    def test_constructing_wrappers_does_not_add_handlers(self):
        target = logging.getLogger("pyccp.repeated")
        handlers = list(target.handlers)
        for _ in range(5):
            Logger("repeated")
        self.assertEqual(target.handlers, handlers)
        self.assertEqual(Logger("repeated").logger.name, "pyccp.repeated")

    def test_application_handler_and_level_configuration(self):
        wrapper = Logger("configuration")
        wrapper.set_level("DEBUG")
        with self.assertLogs("pyccp.configuration", level="DEBUG") as records:
            wrapper.debug("detail")
        self.assertEqual(len(records.records), 1)
        wrapper.silent()
        self.assertEqual(wrapper.logger.level, logging.CRITICAL)
        wrapper.verbose()
        self.assertEqual(wrapper.logger.level, logging.DEBUG)
