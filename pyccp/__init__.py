"""CAN Calibration Protocol tools; applications configure logging handlers."""
import logging

logging.getLogger(__name__).addHandler(logging.NullHandler())
