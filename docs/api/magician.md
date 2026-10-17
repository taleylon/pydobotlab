# Magician

`Magician` controls one Dobot Magician arm. Create an instance, then open the connection with `connect()` or a `with` block. By default, the connection goes through the [control panel](../panel/running.md#scripts), which must be running.

| Member | Description |
|---|---|
| [`Magician`](#magician) | Create a driver for one arm. |
| [`Magician.connect`](#connect) | Open the connection and start the command queue. |
| [`Magician.disconnect`](#disconnect) | Stop the command queue and close the connection. |
| [`Magician.port`](#port) | Port of the connection. |
| [`Magician.is_open`](#is_open) | Whether the connection is open. |
| [`Magician.Stepper1`, `Magician.Stepper2`](#stepper1) | Conveyor motor indices. |
| [`Magician.get_device_serial_number`](#get_device_serial_number) | Read the serial number of the arm. |
| [`Magician.get_device_name`](#get_device_name) | Read the device name. |
| [`Magician.set_device_name`](#set_device_name) | Set the device name. |
| [`Magician.get_device_version`](#get_device_version) | Read the firmware version. |
| [`Dobot`](#dobot) | Alias of `Magician`. |

---

## `Magician` {#magician}

```python
Magician(port=None, baudrate=None, timeout=None, *, auto_start_queue=True, only_known_adapters=False, require_panel=True, via_broker="auto", broker_host=None, broker_port=None, verbose=True)
```

Create a driver for one arm. The connection opens on [`connect`](#connect).

**Parameters**

| Name | Type | Description |
|---|---|---|
| `port` | `str` or `None`, default `None` | Serial port, for example `"COM3"` or `"/dev/ttyUSB0"`. `None` selects the first port that answers as a Dobot. |
| `baudrate` | `int` or `None`, default `None` | Serial baud rate. `None` uses the configured default, `115200` unless changed. |
| `timeout` | `float` or `None`, default `None` | Read timeout per byte, in seconds. `None` uses the configured default, `1.0` unless changed. |
| `auto_start_queue` | `bool`, default `True` | Clear and start the firmware command queue on connect and on disconnect. |
| `only_known_adapters` | `bool`, default `False` | When selecting a port automatically, consider only known Dobot adapters ([`KNOWN_DOBOT_USB_IDS`](discovery.md#known_dobot_usb_ids)). |
| `require_panel` | `bool`, default `True` | `True` connects through the running control panel, that is through its [broker](broker.md), and raises if it is not running. `False` connects through the panel when it is running and opens the port directly otherwise. |
| `via_broker` | `bool` or `"auto"`, default `"auto"` | `"auto"` follows `require_panel`. `True` requires a broker. `False` always opens the port directly; `require_panel` does not apply. |
| `broker_host` | `str` or `None`, default `None` | Broker host. `None` uses the configured default, `"127.0.0.1"` unless changed. |
| `broker_port` | `int` or `None`, default `None` | Broker TCP port. `None` uses the configured default, `8765` unless changed. |
| `verbose` | `bool`, default `True` | Print a line when `connect` succeeds or fails, and when the pose stream fails or recovers. |

Configured defaults are read when the instance is created. See [Configuration](config.md).

**Notes**

`Magician` is a context manager. Entering the block calls `connect` and returns the instance; leaving it calls `disconnect`, including when an exception is raised.

**Example**

```python
from pydobotlab import Magician

with Magician(port="COM3") as bot:
    print(bot.get_pose())
```

---

## `Magician.connect` {#connect}

```python
Magician.connect() -> None
```

Open the connection and prepare the command queue.

Selects a port if none was given, connects through the control panel or directly according to `require_panel` and `via_broker`, then clears and starts the firmware queue when `auto_start_queue=True`. With `verbose=True`, prints `[pydobotlab] Connected to <port>.` on success, or `[pydobotlab] Failed to connect: <reason>` to standard error before raising.

**Raises**

- [`DobotConnectionError`](errors.md#dobotconnectionerror): the control panel is not running (`require_panel=True`), no arm was found, the port could not be opened, or `via_broker=True` and no broker is reachable.
- [`DobotPortInUseError`](errors.md#dobotportinuseerror): the port is open in this process or in another program.
- [`DobotPermissionError`](errors.md#dobotpermissionerror): the operating system denied access to the port.

---

## `Magician.disconnect` {#disconnect}

```python
Magician.disconnect() -> None
```

Stop the pose stream, remove commands left in the firmware queue, and close the connection. With `auto_start_queue=True`, the queue is left running for the control panel or the next program.

Does not raise. If a program exits without calling `disconnect`, the operating system releases the port.

---

## `Magician.port` {#port}

```python
Magician.port: str | None
```

Port of the connection. Before connecting, the port passed to the constructor. Read-only.

---

## `Magician.is_open` {#is_open}

```python
Magician.is_open: bool
```

`True` while the connection is open. Read-only.

---

## `Magician.Stepper1`, `Magician.Stepper2` {#stepper1}

```python
Magician.Stepper1 = 0
Magician.Stepper2 = 1
```

Conveyor motor indices for [`set_converyor`](accessories.md#set_converyor).

---

## `Magician.get_device_serial_number` {#get_device_serial_number}

```python
Magician.get_device_serial_number() -> str
```

Read the serial number of the arm.

---

## `Magician.get_device_name` {#get_device_name}

```python
Magician.get_device_name() -> str
```

Read the device name.

---

## `Magician.set_device_name` {#set_device_name}

```python
Magician.set_device_name(name) -> None
```

Set the device name.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `name` | `str` | New name. ASCII characters only. |

---

## `Magician.get_device_version` {#get_device_version}

```python
Magician.get_device_version() -> tuple[int, int, int]
```

Read the firmware version.

**Returns** `tuple[int, int, int]`: `(major, minor, revision)`.

---

## `Dobot` {#dobot}

Alias of [`Magician`](#magician).
