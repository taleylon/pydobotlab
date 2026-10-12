# Broker

Module `pydobotlab.broker`. A broker is a local TCP server that owns serial ports and relays commands from several `Magician` instances, including instances in other processes. With the default `via_broker="auto"`, [`Magician`](magician.md#magician) connects through a running broker. The control panel starts a broker automatically. The wire protocol is described in [The DobotBroker](../panel/broker.md).

| Member | Description |
|---|---|
| [`DobotBroker`](#dobotbroker) | TCP broker for serial ports. |
| [`DobotBroker.start`](#dobotbroker-start) | Start serving. |
| [`DobotBroker.stop`](#dobotbroker-stop) | Stop serving and close all ports. |
| [`DobotBroker.attach`](#dobotbroker-attach) | Open a port and manage it. |
| [`DobotBroker.detach`](#dobotbroker-detach) | Close a managed port. |
| [`DobotBroker.attached_ports`](#dobotbroker-attached_ports) | List the managed ports. |
| [`is_broker_reachable`](#is_broker_reachable) | Whether a broker accepts connections. |
| [`list_broker_ports`](#list_broker_ports) | List the ports of a running broker. |

---

## `DobotBroker` {#dobotbroker}

```python
class pydobotlab.broker.DobotBroker(host=None, port=None)
```

TCP broker for serial ports. A port that a client requests and that is not attached is opened on demand and closed when its last client disconnects. Ports opened with [`attach`](#dobotbroker-attach) stay open until [`detach`](#dobotbroker-detach) or [`stop`](#dobotbroker-stop).

**Parameters**

| Name | Type | Description |
|---|---|---|
| `host` | `str` or `None`, default `None` | Address to listen on. `None` uses the configured default, `"127.0.0.1"` unless changed. |
| `port` | `int` or `None`, default `None` | TCP port. `None` uses the configured default, `8765` unless changed. `0` selects a free port. |

**Attributes**

| Name | Type | Description |
|---|---|---|
| `host` | `str` | Address to listen on. |
| `port` | `int` | TCP port. After `start`, the port in use. |

**Notes**

`DobotBroker` is a context manager. Entering the block calls `start` and returns the broker; leaving it calls `stop`.

**Example**

```python
from pydobotlab.broker import DobotBroker

with DobotBroker() as broker:
    broker.attach("COM3")
    input("Broker running. Press Enter to stop.")
```

---

## `DobotBroker.start` {#dobotbroker-start}

```python
DobotBroker.start() -> None
```

Start serving on a background thread. Has no effect if the broker is already running.

**Raises**

- `OSError`: the address is already in use.

---

## `DobotBroker.stop` {#dobotbroker-stop}

```python
DobotBroker.stop() -> None
```

Stop serving and close all attached ports.

---

## `DobotBroker.attach` {#dobotbroker-attach}

```python
DobotBroker.attach(port, *, baudrate=None, timeout=None) -> SerialTransport
```

Open `port` and manage it until [`detach`](#dobotbroker-detach) or [`stop`](#dobotbroker-stop). Returns the existing transport if the port is already attached.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `port` | `str` | Serial port. |
| `baudrate` | `int` or `None`, default `None` | Serial baud rate. `None` uses the configured default, as for [`Magician`](magician.md#magician). |
| `timeout` | `float` or `None`, default `None` | Read timeout per byte, seconds. `None` uses the configured default. |

**Returns** `SerialTransport`: the open transport.

**Raises**

- [`DobotConnectionError`](errors.md#dobotconnectionerror) and its subclasses: the port could not be opened.

---

## `DobotBroker.detach` {#dobotbroker-detach}

```python
DobotBroker.detach(port) -> None
```

Close `port` and stop managing it. Has no effect if the port is not attached.

---

## `DobotBroker.attached_ports` {#dobotbroker-attached_ports}

```python
DobotBroker.attached_ports() -> list[str]
```

Return the attached ports, sorted.

---

## `is_broker_reachable` {#is_broker_reachable}

```python
pydobotlab.broker.is_broker_reachable(host=None, port=None, timeout=None) -> bool
```

Return whether a broker accepts connections at `host:port`. A result is reused for a short time.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `host` | `str` or `None`, default `None` | Broker host. `None` uses the configured default. |
| `port` | `int` or `None`, default `None` | Broker TCP port. `None` uses the configured default. |
| `timeout` | `float` or `None`, default `None` | Connection timeout, seconds. `None` uses the configured default, `0.15` unless changed. |

---

## `list_broker_ports` {#list_broker_ports}

```python
pydobotlab.broker.list_broker_ports(host=None, port=None, timeout=None) -> list[str]
```

Return the ports attached to a running broker.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `host` | `str` or `None`, default `None` | Broker host. `None` uses the configured default. |
| `port` | `int` or `None`, default `None` | Broker TCP port. `None` uses the configured default. |
| `timeout` | `float` or `None`, default `None` | Socket timeout, seconds. `None` uses the configured default, `1.0` unless changed. |

**Raises**

- `OSError`: no broker is reachable.
