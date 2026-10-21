[![CI](https://github.com/vpetrigo/pyccp/actions/workflows/ci.yml/badge.svg)](https://github.com/vpetrigo/pyccp/actions/workflows/ci.yml)
[![PyPI - Version](https://img.shields.io/pypi/v/pyccp)](https://pypi.org/project/pyccp)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/pyccp)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/pyccp?period=monthly&units=INTERNATIONAL_SYSTEM&left_color=GREY&right_color=GREEN&left_text=downloads%2Fmonth)](https://pepy.tech/projects/pyccp)

# CAN Calibration Protocol for Python

A Python CAN Calibration Protocol (CCP) based on protocol version 2.1 master
using [python-can](https://python-can.readthedocs.io/).

## Install

Add into the `pyproject.toml`:

```toml
dependencies = [
    "pyccp==0.10.0"
]
```

## Running tests

Execute the following command to run the tests:

```sh
hatch test
```

If you want to run only a specific version of Python, you can use the `-py` option:

```sh
hatch test -py 3.14
```

## Example

```python
import logging
import can
from pyccp import Master

logging.basicConfig(level=logging.WARNING)  # Library does not install stream handlers.
bus = can.Bus(interface="socketcan", channel="can0")
master = Master(bus, cro=0x7E1, dto=0x815)


def require_ack(response):
    if response is None:
        raise TimeoutError("CCP response timed out")
    if response[1] != 0:
        raise RuntimeError(f"CCP error: {response[1]:#04x}")
    return response


try:
    require_ack(master.connect(0x7E1, address=0x39))
    # Perform the target ECU's seed/key authorization and preparation as required.
    require_ack(master.set_mta(0x7E1, address=0x1000))
    require_ack(master.clear_memory(0x7E1, block_size=9))
    require_ack(master.program6(0x7E1, b"abcdef"))  # Exactly 6 bytes, no size byte.
    require_ack(master.program(0x7E1, b"ghi"))  # 1–5 bytes.
    require_ack(master.program(0x7E1, b""))  # PROGRAM(size=0): terminate.
finally:
    master.shutdown()
```

## Logging setup

```python
import logging

logger = logging.getLogger("pyccp")
logger.setLevel(logging.DEBUG)

handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
logger.addHandler(handler)
```
