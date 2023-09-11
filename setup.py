#!/bin/env python

import os
from setuptools import setup


setup(
    name='pyccp',
    version='0.9.0',
    description="CAN Calibration Protocol for Python",
    author='Christoph Schueler',
    author_email='cpu12.gems@googlemail.com',
    url='http://github.com/pySART/pyccp',
    packages=['pyccp'],
    test_suite="pyccp.tests"
)
