# Errors & exceptions

Every error pydobotlab raises descends from `DobotError`, so a single `except DobotError` catches them all. The hierarchy is:

```
DobotError
├── DobotConnectionError
│   └── DobotPortInUseError
├── DobotProtocolError
├── DobotTimeoutError
├── DobotAlarmError
│   └── DobotKinematicError
```

Import them from `pydobotlab.errors` (re-exported at top level for convenience):

```python
from pydobotlab.errors import (
    DobotError,
    DobotConnectionError,
    DobotPortInUseError,
    DobotProtocolError,
    DobotTimeoutError,
    DobotAlarmError,
    DobotKinematicError,
)
```

---

## `DobotError`

Base class - never raised directly. Catch this if you want to handle "anything pydobotlab can fail with".

---

## `DobotConnectionError`

Could not open / read / write the serial port (or the broker socket).

**Common causes.**
* Port doesn't exist (cable unplugged, wrong COM name).
* Permission denied (Linux: not in `dialout` group).
* Underlying read/write blew up after the port was open.

---

## `DobotPortInUseError` *(extends `DobotConnectionError`)*

The requested serial port is already claimed:
* …by another `Magician` instance **in this process** (caught eagerly via the in-process registry), *or*
* …by another OS process (POSIX exclusive `flock` conflict, or Windows file-share denial).

If you see this and don't expect it: check whether the control panel is already running, or whether a previous run didn't disconnect cleanly.

---

## `DobotProtocolError`

A malformed or unexpected packet was received from the arm - bad frame header, length mismatch, or bad checksum. pydobotlab's reader resyncs on bad headers, so this generally means the wire was *very* corrupted (cable issue, baud-rate mismatch).

---

## `DobotTimeoutError`

A command did not receive a response within the configured timeout. Most often raised by:
* `wait_for(index, timeout=...)` when the firmware queue didn't reach `index` in time.
* The transport when a frame read or write itself timed out.

---

## `DobotAlarmError`

The arm reported one or more alarms while a command was pending. Constructor:

```python
class DobotAlarmError(DobotError):
    def __init__(self, alarms: list[str] | None = None, message: str = ""): ...
```

* `alarms` - list of alarm names that were active.
* The default message is `f"Dobot alarms active: {self.alarms}"`; you can override.

Raised by [`ensure_no_alarms()`](alarms.md#ensure_no_alarms-none) and by [`clear_alarm(verify=True)`](alarms.md#clear-alarm) when the alarm reasserts itself after clearing.

---

## `DobotKinematicError` *(extends `DobotAlarmError`)*

A motion command failed because the firmware couldn't plan or execute it. Specifically, one of these alarms fired while a motion was pending:

* `PLAN_INVERSE_RESOLVE` - IK solver couldn't find a solution.
* `PLAN_MOTION_TARGET_OUT_OF_WORKSPACE` - target outside reach.
* `KINEMATIC_TARGET_OUT_OF_WORKSPACE` - same, kinematic side.
* `PLAN_INVERSE_LIMIT` / `KINEMATIC_INVERSE_LIMIT` - IK hit a joint limit.
* `PLAN_IN_SINGULARITY_ZONE` / `KINEMATIC_SINGULARITY` - singular pose.
* `PLAN_CURRENT_JOINT_OUT_OF_RANGE` - start pose already off-range.
* `LIMIT_POS_J*` / `LIMIT_NEG_J*` - joint limit struck mid-motion.

The exception's `str()` includes one `"{TAG}: {explanation + how to fix}"` line per active alarm, plus the recovery instruction:

> Recover by calling `clear_alarm()` (or `set_home()` if you want to also re-zero the arm) before retrying.

Raised by [`move_to`](motion.md#move-to), [`set_home`](motion.md#set_home-waittrue-timeout600-raise_on_alarmtrue-int), [`wait_for`](queue.md#wait_forindex-timeoutnone-poll002-raise_on_alarmtrue-none), [`wait_idle`](queue.md#wait_idle-timeoutnone-poll002-raise_on_alarmtrue-none).

---

## Recovering from errors

```python
from pydobotlab import Magician
from pydobotlab.errors import DobotKinematicError, DobotAlarmError

with Magician() as bot:
    try:
        bot.move_to(9999, 0, 0, 0)
    except DobotKinematicError as e:
        print(e)  # has the troubleshoot lines
        bot.clear_alarm()  # back to a clean state
        # …optionally retry with a reachable target…
    except DobotAlarmError as e:
        print("non-motion alarm:", e.alarms)
        bot.clear_alarm()
```

For the user-facing equivalent inside the panel, see [Control Panel](../panel/overview.md).
