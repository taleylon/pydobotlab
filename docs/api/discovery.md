# Discovery

Find serial ports and probe them for Dobot Magician arms. The functions are also available as static methods of [`Discovery`](#discovery).

A port is identified as a Dobot Magician when it answers three read requests in the formats of the [Communication Protocol](../Dobot-Communication-Protocol-V1.1.5.pdf). The protocol has no command that reports the model. The requests do not move the arm or change its state.

| Request | Expected reply | Protocol |
|---|---|---|
| `GetDeviceSN` | Command ID 0 and the serial number. | Table 6 |
| `GetDeviceVersion` | Command ID 2 and three version bytes. | Table 12 |
| `GetPose` | Command ID 10 and eight finite floats: X, Y, Z, R, and the four joint angles. | Table 22 |

| Member | Description |
|---|---|
| [`list_ports`](#list_ports) | List serial ports. |
| [`is_dobot`](#is_dobot) | Probe one port. |
| [`discover`](#discover) | Probe all ports and return the arms found. |
| [`discover_with_diagnostics`](#discover_with_diagnostics) | Probe all ports and return the arms found and the failures. |
| [`find_free_port`](#find_free_port) | Return the first available arm port. |
| [`is_port_in_use`](#is_port_in_use) | Whether a port is open in this process. |
| [`Discovery`](#discovery) | Namespace of the discovery functions. |
| [`PortInfo`](#portinfo) | Serial port description. |
| [`DiscoveredDobot`](#discovereddobot) | Port identified as a Dobot Magician. |
| [`ProbeFailure`](#probefailure) | Port that failed the probe. |
| [`KNOWN_DOBOT_USB_IDS`](#known_dobot_usb_ids) | USB IDs of known Dobot adapters. |

---

## `list_ports` {#list_ports}

```python
pydobotlab.list_ports(*, only_known_adapters=False) -> list[PortInfo]
```

List serial ports. Known Dobot adapters are listed first. No data is sent to the ports.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `only_known_adapters` | `bool`, default `False` | List only ports whose USB VID and PID are in [`KNOWN_DOBOT_USB_IDS`](#known_dobot_usb_ids). |

**Returns** `list` of [`PortInfo`](#portinfo).

---

## `is_dobot` {#is_dobot}

```python
pydobotlab.is_dobot(port, *, timeout=None) -> bool
```

Return whether a Dobot Magician answers on `port`. Returns `True` for a port already open in this process.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `port` | `str` | Serial port. |
| `timeout` | `float` or `None`, default `None` | Reply timeout, seconds. `None` uses the configured default, `0.4` unless changed. |

---

## `discover` {#discover}

```python
pydobotlab.discover(*, only_known_adapters=False, timeout=None, skip=()) -> list[DiscoveredDobot]
```

Probe all ports and return those identified as a Dobot Magician. Ports open in this process are skipped.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `only_known_adapters` | `bool`, default `False` | Probe only ports whose USB VID and PID are in [`KNOWN_DOBOT_USB_IDS`](#known_dobot_usb_ids). |
| `timeout` | `float` or `None`, default `None` | Reply timeout per port, seconds. `None` uses the configured default, `0.4` unless changed. |
| `skip` | iterable of `str`, default `()` | Ports not to probe. |

**Returns** `list` of [`DiscoveredDobot`](#discovereddobot).

**Example**

```python
ports = {arm.serial_number: arm.port for arm in discover()}
left = Magician(port=ports["MAG-001"])
```

---

## `discover_with_diagnostics` {#discover_with_diagnostics}

```python
pydobotlab.discover_with_diagnostics(*, only_known_adapters=False, timeout=None, skip=()) -> tuple[list[DiscoveredDobot], list[ProbeFailure]]
```

Probe all ports and return the arms found and the ports that failed. Parameters are the same as for [`discover`](#discover).

**Returns** `tuple`: `(found, failures)`, a list of [`DiscoveredDobot`](#discovereddobot) and a list of [`ProbeFailure`](#probefailure).

**Example**

```python
found, failures = discover_with_diagnostics()
for failure in failures:
    print(failure.port, failure.reason, failure.detail)
```

---

## `find_free_port` {#find_free_port}

```python
pydobotlab.find_free_port(*, only_known_adapters=False) -> str | None
```

Return the first port identified as a Dobot Magician and not open in this process, or `None`.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `only_known_adapters` | `bool`, default `False` | Probe only ports whose USB VID and PID are in [`KNOWN_DOBOT_USB_IDS`](#known_dobot_usb_ids). |

---

## `is_port_in_use` {#is_port_in_use}

```python
pydobotlab.is_port_in_use(port) -> bool
```

Return whether `port` is open by a `Magician` in this process. A port held by another process is reported by [`connect`](magician.md#connect) as [`DobotPortInUseError`](errors.md#dobotportinuseerror).

---

## `Discovery` {#discovery}

```python
class pydobotlab.Discovery
```

Namespace that exposes the discovery functions as static methods: `Discovery.list_ports`, `Discovery.is_dobot`, `Discovery.discover`, `Discovery.discover_with_diagnostics`, `Discovery.find_free_port`, and `Discovery.is_port_in_use`.

---

## `PortInfo` {#portinfo}

```python
class pydobotlab.PortInfo(port, description="", vid=None, pid=None, serial_number=None, is_known_dobot_adapter=False, is_claimed=False)
```

Serial port returned by [`list_ports`](#list_ports). Immutable.

| Attribute | Type | Description |
|---|---|---|
| `port` | `str` | Port name. |
| `description` | `str` | Description from the operating system. |
| `vid`, `pid` | `int` or `None` | USB vendor and product IDs. |
| `serial_number` | `str` or `None` | Serial number of the USB adapter. |
| `is_known_dobot_adapter` | `bool` | VID and PID belong to a known Dobot adapter ([`KNOWN_DOBOT_USB_IDS`](#known_dobot_usb_ids)). |
| `is_claimed` | `bool` | The port is open by a `Magician` in this process. |

---

## `DiscoveredDobot` {#discovereddobot}

```python
class pydobotlab.DiscoveredDobot(port, serial_number, description="")
```

Port identified as a Dobot Magician. Immutable.

| Attribute | Type | Description |
|---|---|---|
| `port` | `str` | Port name. |
| `serial_number` | `str` | Serial number of the arm. |
| `description` | `str` | Description from the operating system. |

---

## `ProbeFailure` {#probefailure}

```python
class pydobotlab.ProbeFailure(port, description, reason, detail)
```

Port that failed the probe in [`discover_with_diagnostics`](#discover_with_diagnostics). Immutable.

| Attribute | Type | Description |
|---|---|---|
| `port` | `str` | Port name. |
| `description` | `str` | Description from the operating system. |
| `reason` | `str` | `"permission"`: access denied by the operating system. `"busy"`: the port is held by another program. `"no_reply"`: the port opened but did not answer as a Dobot Magician. `"other"`: any other failure. |
| `detail` | `str` | Error message. |

---

## `KNOWN_DOBOT_USB_IDS` {#known_dobot_usb_ids}

```python
pydobotlab.KNOWN_DOBOT_USB_IDS: set[tuple[int, int]]
```

USB `(vid, pid)` pairs of known Dobot adapters. Contains `(0x1A86, 0x7523)` (WCH CH340) by default. Add pairs to recognize other adapters.

**Example**

```python
KNOWN_DOBOT_USB_IDS.add((0x10C4, 0xEA60))
```
