# Discovery (finding arms)

`pydobotlab.discovery` is the small module that figures out which serial ports might be Dobots and probes them. Almost everyone uses it indirectly via `Magician(port=None)`, but it's also exposed as a direct API for the cases where you want to enumerate, label, or steer arms by serial number.

Both module-level functions and a `Discovery` class namespace are exported; they're exactly equivalent.

```python
from pydobotlab import (
    Discovery,
    list_ports,
    discover,
    discover_with_diagnostics,
    find_free_port,
    is_dobot,
    is_port_in_use,
)
```

---

## `list_ports(*, only_known_adapters=False) -> list[PortInfo]`

**Purpose.** Enumerate serial ports the OS sees, flag the ones whose USB VID/PID matches a known Dobot adapter, and tell you which are already claimed by a Magician instance in this process.

**Inputs.**

| Arg | Type | Default | Meaning |
|-----|------|---------|---------|
| `only_known_adapters` | `bool` | `False` | If `True`, drop ports whose USB VID/PID is not in `KNOWN_DOBOT_USB_IDS`. Defaults to `False` so a Dobot behind a not-yet-seen adapter still shows up. |

**Returns.** `list[PortInfo]`. Sorted with known-adapter ports first.

**No protocol I/O** - this is a pure OS enumeration. No frames are sent.

---

## `is_dobot(port, *, timeout=0.4) -> bool`

**Purpose.** Quickly probe one port to see whether a Dobot answers.

**Inputs.**

| Arg | Type | Default | Meaning |
|-----|------|---------|---------|
| `port` | `str` | – | OS device path / COM name. |
| `timeout` | `float` | `0.4` | Seconds to wait for a reply. |

**Returns.** `bool`.

**Protocol.** Opens the port, sends [`GET_DEVICE_SN`](../protocol/command-ids.md) (0) read + immediate, returns `True` if a well-formed response comes back.

---

## `discover(*, only_known_adapters=False, timeout=0.4, skip=()) -> list[DiscoveredDobot]`

**Purpose.** Probe every candidate port and return the ones that answered like a Dobot, with each one's serial number.

**Inputs.**

| Arg | Type | Default | Meaning |
|-----|------|---------|---------|
| `only_known_adapters` | `bool` | `False` | Same meaning as in `list_ports`. |
| `timeout` | `float` | `0.4` | Per-port probe timeout. |
| `skip` | iterable of `str` | `()` | Ports to skip (e.g. ones you've already opened elsewhere). |

**Returns.** `list[DiscoveredDobot]`. Each entry has `.port`, `.serial_number`, `.description`.

**Protocol.** Same probe as `is_dobot()` per port - [`GET_DEVICE_SN`](../protocol/command-ids.md) (0).

**Example - pin specific arms by serial:**

```python
from pydobotlab import discover, Magician

machines = {h.serial_number: h.port for h in discover()}
left = Magician(port=machines["MAG-001"])
right = Magician(port=machines["MAG-002"])
```

---

## `discover_with_diagnostics(*, only_known_adapters=False, timeout=0.4, skip=()) -> tuple[list[DiscoveredDobot], list[ProbeFailure]]`

**Purpose.** Same as [`discover`](#discover-only_known_adaptersfalse-timeout04-skip-listdiscovereddobot), but also returns the list of ports that were *tried* but didn't qualify, with a reason for each. Useful for telling a user *why* a particular port didn't show up rather than silently dropping it.

This is what the panel hub uses, so that ttyACM ports on Linux are surfaced with the relevant fix-it message instead of just disappearing. See [Linux setup](../getting-started/linux.md) for the common ttyACM gotchas (dialout group, brltty hijacking).

**Inputs.** Same as `discover()`.

**Returns.** `(hits, failures)` - `hits: list[DiscoveredDobot]`, `failures: list[`[`ProbeFailure`](#probefailure)`]`.

**Example.**

```python
from pydobotlab import Discovery

hits, failures = Discovery.discover_with_diagnostics()
print("found:", hits)
for f in failures:
    print(f"  rejected {f.port}: {f.reason} - {f.detail}")
```

---

## `find_free_port(*, only_known_adapters=False) -> str | None`

**Purpose.** Return the first available Dobot port (enumerated by the OS, not in use, and answering `GET_DEVICE_SN`), or `None`.

**Returns.** `str | None`.

---

## `is_port_in_use(port) -> bool`

**Purpose.** `True` if `port` is currently held by a `Magician` in *this process*. (Cross-process collisions are caught at `connect()` time and surface as [`DobotPortInUseError`](errors.md#dobotportinuseerror-extends-dobotconnectionerror).)

**Returns.** `bool`. No protocol I/O.

---

## `PortInfo`

| Field | Type | Meaning |
|-------|------|---------|
| `port` | `str` | OS device name. |
| `description` | `str` | OS-supplied description (e.g. `"USB Serial - CH340"`). |
| `vid, pid` | `int \| None` | USB vendor / product IDs. |
| `serial_number` | `str \| None` | USB descriptor SN (the cable's, not the arm's). |
| `is_known_dobot_adapter` | `bool` | VID/PID is in `KNOWN_DOBOT_USB_IDS`. |
| `is_claimed` | `bool` | Already opened by a `Magician` in this process. |

## `DiscoveredDobot`

| Field | Type | Meaning |
|-------|------|---------|
| `port` | `str` | OS device name. |
| `serial_number` | `str` | The **arm's** serial number (returned by `GET_DEVICE_SN`). Use this to pin specific arms across reboots. |
| `description` | `str` | Forwarded from `PortInfo`. |

## `ProbeFailure`

Returned by `discover_with_diagnostics()` for each port that was tried but didn't pass the probe.

| Field | Type | Meaning |
|-------|------|---------|
| `port` | `str` | OS device name. |
| `description` | `str` | Forwarded from `PortInfo`. |
| `reason` | `str` | One of: `"permission"` (e.g. dialout group missing), `"busy"` (held by another process / brltty), `"no_reply"` (port opened but the device didn't respond like a Dobot), `"other"`. |
| `detail` | `str` | Full error message. |

## `KNOWN_DOBOT_USB_IDS`

Settable `set[tuple[int, int]]` of `(vid, pid)` pairs treated as Dobot adapters. The default contains `(0x1A86, 0x7523)` (WCH CH340 - every Magician seen in the wild). Extend at runtime if your hardware revision uses a different adapter:

```python
from pydobotlab.discovery import KNOWN_DOBOT_USB_IDS

KNOWN_DOBOT_USB_IDS.add((0x10C4, 0xEA60))
```
