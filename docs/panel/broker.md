# The DobotBroker

The broker is a tiny TCP server that lets several clients (the panel, your script, a logger, …) share one serial port without stepping on each other. It runs on `127.0.0.1:8765` by default and is auto-spawned by the panel when no broker is reachable.

```
┌────────────┐  TCP   ┌──────────────────┐  serial  ┌────────┐
│ ControlPanel│──────►│   DobotBroker    │─────────►│  arm   │
│ (Magician)  │        │  per-port refcnt │          └────────┘
└────────────┘        │   ATTACH/SEND    │
                      └────────▲─────────┘
┌────────────┐  TCP            │
│ your script │────────────────┘
│ (Magician)  │
└────────────┘
```

`Magician(via_broker="auto")` (the default) uses the broker if one is reachable; otherwise it opens the serial port directly.

## Wire protocol (broker-side, not the Dobot protocol)

> This is the protocol *between* `Magician` and the broker. The Dobot frames are tunneled inside it.

### ATTACH handshake

Client → broker: `0x01 | u8 N | port[N]` (port name as ASCII).

Broker → client (single byte):
* `0x00` - attached. Subsequent traffic is request/response framing (below).
* `0x01` - broker has no transport for that port and could not open one.
* `0x02` - port is busy.

### Per-frame request/response

Client → broker: `u16 LEN (big-endian) | DOBOT_FRAME[LEN]`.

Broker → client: `u16 LEN (big-endian) | DOBOT_FRAME[LEN]`.

The Dobot frames inside this tunnel are exactly the [wire frames](../protocol/frame-format.md) `Magician` would otherwise send straight to the serial port - the broker just forwards them and reads the reply.

## Reference counting

When N clients ATTACH to the same port, the broker's per-port `SerialTransport` is opened on first attach and closed on the *last* detach. This is how the panel can come and go without dropping the script's connection.

`broker.list_broker_ports(host, port)` lets a `Magician` ask the broker which ports it currently owns.

## Python entry points

```python
from pydobotlab import broker

broker.is_broker_reachable("127.0.0.1", 8765)  # bool
broker.list_broker_ports("127.0.0.1", 8765)  # list[str]
```

The broker object itself (`DobotBroker`) is also instantiable if you want to host your own - though normally the panel does it for you:

```python
from pydobotlab.broker import DobotBroker

b = DobotBroker(host="127.0.0.1", port=8765)
b.start()  # background thread; non-blocking
# … later …
b.stop()
```

## When *not* to use the broker

* Tight benchmarks where the extra TCP hop matters (`via_broker=False`).
* Embedded contexts where you can't open a TCP port.

## Implementation notes

* The broker uses a single `serial.Serial` per port internally and serialises requests on a per-port lock. This means N clients sharing one port pay the cost of one serial round-trip per request, but never get partial frames.
* On first ATTACH for a previously-unknown port, the broker tries to open it lazily with the same `SerialTransport(exclusive=True)` settings `Magician` would use directly.
* Source: `pydobotlab/broker.py`.
