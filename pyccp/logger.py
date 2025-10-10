#!/usr/bin/env python
# -*- coding: utf-8 -*-

__copyright__ = """
    pySART - Simplified AUTOSAR-Toolkit for Python.

   (C) 2009-2016 by Christoph Schueler <cpu12.gems@googlemail.com>

   All Rights Reserved

  This program is free software; you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation; either version 2 of the License, or
  (at your option) any later version.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License along
  with this program; if not, write to the Free Software Foundation, Inc.,
  51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""

import logging

from pyccp.utils import SingletonBase


class Logger(SingletonBase):
    LOGGER_BASE_NAME = "pyccp"
    FORMAT = "[%(levelname)s (%(name)s)]: %(message)s"

    def __init__(self, name, level=logging.WARN):
        self.logger = logging.getLogger("{0}.{1}".format(self.LOGGER_BASE_NAME, name))
        self.logger.setLevel(level)
        handler = logging.StreamHandler()
        handler.setLevel(level)
        formatter = logging.Formatter(self.FORMAT)
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.last_message = None
        self.last_severity = None

    def get_last_error(self):
        result = (self.last_severity, self.last_message)
        self.last_severity = self.last_message = None
        return result

    def log(self, message, level):
        self.last_severity = level
        self.last_message = message
        self.logger.log(level, "{0}".format(message))

    def info(self, message):
        self.log(message, logging.INFO)

    def warn(self, message):
        self.log(message, logging.WARN)

    def debug(self, message):
        self.log(message, logging.DEBUG)

    def error(self, message):
        self.log(message, logging.ERROR)

    def critical(self, message):
        self.log(message, logging.CRITICAL)

    def verbose(self):
        self.logger.setLevel(logging.DEBUG)

    def silent(self):
        self.logger.setLevel(logging.CRITICAL)

    def set_level(self, level):
        LEVEL_MAP = {
            "INFO": logging.INFO,
            "WARN": logging.WARN,
            "DEBUG": logging.DEBUG,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        if isinstance(level, str):
            level = LEVEL_MAP.get(level.upper(), logging.WARN)
        self.logger.setLevel(level)
