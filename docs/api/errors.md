# Exceptions

All exceptions derive from `DobotError` and are importable from `pydobotlab` and `pydobotlab.errors`.

```text
DobotError
├── DobotConfigError
├── DobotConnectionError
│   ├── DobotPortInUseError
│   └── DobotPermissionError
├── DobotProtocolError
├── DobotTimeoutError
└── DobotAlarmError
    ├── DobotKinematicError
    ├── DobotOverspeedError
    ├── DobotLostStepError
    └── DobotSystemAlarmError
```

| Exception | Description |
|---|---|
| [`DobotError`](#doboterror) | Base class. |
| [`DobotConfigError`](#dobotconfigerror) | The configuration file is invalid. |
| [`DobotConnectionError`](#dobotconnectionerror) | The connection could not be opened or used. |
| [`DobotPortInUseError`](#dobotportinuseerror) | The port is busy. |
| [`DobotPermissionError`](#dobotpermissionerror) | Access to the port was denied. |
| [`DobotProtocolError`](#dobotprotocolerror) | A malformed frame was received. |
| [`DobotTimeoutError`](#dobottimeouterror) | A response or wait timed out. |
| [`DobotAlarmError`](#dobotalarmerror) | The arm reported an alarm. |
| [`DobotKinematicError`](#dobotkinematicerror) | A planning, motion, or limit alarm. |
| [`DobotOverspeedError`](#dobotoverspeederror) | A joint over-speed alarm. |
| [`DobotLostStepError`](#dobotloststeperror) | A lost-step alarm. |
| [`DobotSystemAlarmError`](#dobotsystemalarmerror) | A system alarm. |

---

## `DobotError` {#doboterror}

Base class of all pydobotlab exceptions.

---

## `DobotConfigError` {#dobotconfigerror}

The [configuration file](config.md) is invalid. The message names the file and the setting. Raised by the first use of any object that reads a default setting.

---

## `DobotConnectionError` {#dobotconnectionerror}

The serial port or broker connection could not be opened, read, or written, a command was sent while not connected, or the control panel is not running (see `require_panel` in [`Magician`](magician.md#magician)).

---

## `DobotPortInUseError` {#dobotportinuseerror}

Subclass of [`DobotConnectionError`](#dobotconnectionerror). The port is open in this process or held by another program. The message has the form `port 'COM3' is busy`.

---

## `DobotPermissionError` {#dobotpermissionerror}

Subclass of [`DobotConnectionError`](#dobotconnectionerror). The operating system denied access to the port (Linux and macOS). The message names the condition and its remedy:

- The user is not in the group of the device, for example `dialout` on Ubuntu and Debian or `uucp` on Arch Linux.
- The user was added to the group after the current session started.
- The user is in the group and access is still denied.
- The group has no read and write permission on the device.

---

## `DobotProtocolError` {#dobotprotocolerror}

A malformed frame was received: invalid header, length, or checksum.

---

## `DobotTimeoutError` {#dobottimeouterror}

No response arrived within the read timeout, or a wait exceeded its `timeout`. Raised by any command and by [`wait_for`](queue.md#wait_for), [`wait_idle`](queue.md#wait_idle), and [`move_to`](motion.md#move_to).

---

## `DobotAlarmError` {#dobotalarmerror}

```python
DobotAlarmError(alarms=None, message="")
```

The arm reported an alarm. Raised by every DobotLab function that changes the arm state, such as [`ptp`](motion.md#ptp), and by [`move_to`](motion.md#move_to), [`wait_for`](queue.md#wait_for), [`wait_idle`](queue.md#wait_idle), [`batch`](queue.md#batch), [`clear_alarm`](alarms.md#clear_alarm), and [`ensure_no_alarms`](alarms.md#ensure_no_alarms). The arm refuses further commands until the alarm is cleared with [`clear_alarm`](alarms.md#clear_alarm) or the panel's Clear Alarm button. See [Alarms and recovery](../guide/alarms.md).

The subclass follows the group of the alarm, as listed under [Alarm groups](alarms.md#alarm-groups). The message lists each active alarm with a remedy.

| Attribute | Type | Description |
|---|---|---|
| `alarms` | `list[str]` | Names of the active alarms. |

---

## `DobotKinematicError` {#dobotkinematicerror}

Subclass of [`DobotAlarmError`](#dobotalarmerror). A planning, motion, or limit alarm (`PLAN_*`, `MOVE_*`, `LIMIT_*`), for example a target outside the [workspace](../guide/workspace.md).

---

## `DobotOverspeedError` {#dobotoverspeederror}

Subclass of [`DobotAlarmError`](#dobotalarmerror). A joint exceeded its maximum speed (`OVERSPEED_J1` to `OVERSPEED_J4`).

---

## `DobotLostStepError` {#dobotloststeperror}

Subclass of [`DobotAlarmError`](#dobotalarmerror). A joint lost steps (`LOST_STEP_J1` to `LOST_STEP_J4`).

---

## `DobotSystemAlarmError` {#dobotsystemalarmerror}

Subclass of [`DobotAlarmError`](#dobotalarmerror). The arm reported a system fault (`PUBLIC_RESET` to `PUBLIC_ANGLE_SENSOR_READ`).
