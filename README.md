[![CI](https://github.com/vpetrigo/pyccp/actions/workflows/ci.yml/badge.svg)](https://github.com/vpetrigo/pyccp/actions/workflows/ci.yml)
[![PyPI - Version](https://img.shields.io/pypi/v/pyccp)](https://pypi.org/project/pyccp)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/pyccp)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/pyccp?period=monthly&units=INTERNATIONAL_SYSTEM&left_color=GREY&right_color=GREEN&left_text=downloads%2Fmonth)](https://pepy.tech/projects/pyccp)

# CAN Calibration Protocol for Python

Python implementation of the CAN Calibration Protocol (CCP) v2.1, built
on [python-can](https://python-can.readthedocs.io/). Inspired by [pySART/pyccp](https://github.com/pySART/pyccp).

## Install

```toml
dependencies = [
    "pyccp==0.10.0"
]
```

## Quick Start

```python
import can
from pyccp import Master
from pyccp.ccp import ReturnCodes

bus = can.Bus(interface="socketcan", channel="can0")

with Master(bus, cro=0x7E1, dto=0x815) as master:
    resp = master.connect(address=0x39)
    assert resp is not None and resp.code == ReturnCodes.ACKNOWLEDGE

    resp = master.set_mta(address=0x1000)
    assert resp is not None and resp.code == ReturnCodes.ACKNOWLEDGE

    resp = master.clear_memory(block_size=0x200)
    chunks = [b"abcdef", b"ghi", b""]

    for chunk in chunks:
        resp = master.program6(chunk)
        assert resp is not None and resp.code == ReturnCodes.ACKNOWLEDGE
```

## DAQ & Events

```python
from pyccp import Master, DAQMessage, DTO

with Master(bus, cro=0x7E1, dto=0x815) as master:
    # Register a callback for DAQ messages
    master.on_daq(
        0x816,
        lambda msg: print(
            f"DAQ: 0x{msg.daq_id:04X}, ODT: {msg.pid}, data: {msg.data.hex()}"
        ),
    )
    # Connect and configure DAQ list
```

## Client

The `Client` class provides a lower-level, handler-based interface for CCP
client-side operations. It manages a background receiver thread and separate
sender threads for DTO and DAQ messages.

### Basic usage

```python
import can
from pyccp import Client
from pyccp.ccp import CONNECT, GET_CCP_VERSION

bus = can.Bus(interface="socketcan", channel="can0")

with Client(bus, cro=0x7E1, dto=0x815, station_id=0x39) as client:
    client.register_handler(CONNECT.code, lambda cro: dto_ack)
    client.register_handler(GET_CCP_VERSION.code, lambda cro: dto_version)
    # send/receive CCP commands via the registered handlers
```

### Registering a handler

Each handler receives a `CRO` and must return a `DTO` response.

```python
from pyccp.ccp import CONNECT, CRO, DTO, ReturnCodes


def on_connect(cro: CRO) -> DTO:
    # process the connect request
    return DTO(code=ReturnCodes.ACKNOWLEDGE, data=b"\x00\x00\x00\x00\x00\x00")


client.register_handler(CONNECT.code, on_connect)
```

### Sending DAQ messages

```python
from pyccp.ccp import DAQMessage

msg = DAQMessage(daq_id=0x816, pid=0, data=b"\x01\x02\x03\x04")
client.send_daq(msg)
```

## Logging

```python
import logging

logging.getLogger("pyccp").setLevel(logging.DEBUG)
```

## Tests

```sh
hatch test -py 3.15
```
