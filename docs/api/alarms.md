# Alarms

The arm reports faults as a 16-byte (128-bit) bitmask. Each bit is a named alarm code (`0x00..0x7F`); `byte_index = code // 8`, `bit_index = code % 8`. pydobotlab decodes that mask into a friendly [`AlarmSet`](#alarmset) with names *and* per-alarm troubleshoot lines.

When motion alarms fire, pydobotlab surfaces them as [`DobotKinematicError`](errors.md#dobotkinematicerror-extends-dobotalarmerror) from the waiters in [`move_to`](motion.md#move-to) / [`set_home`](motion.md#set_home-waittrue-timeout600-raise_on_alarmtrue-int) / [`wait_for`](queue.md#wait_forindex-timeoutnone-poll002-raise_on_alarmtrue-none) / [`wait_idle`](queue.md#wait_idle-timeoutnone-poll002-raise_on_alarmtrue-none), so you don't sit on a `wait_for` forever for a command the firmware has refused.

---

## `get_alarms() -> AlarmSet`

**Purpose.** Read and decode the firmware's 16-byte alarm bitmask.

**Inputs.** None.

**Returns.** [`AlarmSet`](#alarmset).

**Protocol.** [`GET_ALARMS_STATE`](../protocol/command-ids.md) (20), read + immediate. Response: 16 raw bytes (the mask).

**Example.**

```python
alarms = bot.get_alarms()
if alarms:
    for line in alarms.format():
        print(" •", line)
```

---

## `clear_alarm(*, verify=False, settle=0.15) -> None` {#clear-alarm}

**Purpose.** Clear all active alarms.

**Inputs.**

| Arg | Type | Default | Meaning |
|-----|------|---------|---------|
| `verify` | `bool` | `False` | After clearing, sleep `settle` seconds and re-poll. If any *motion-related* alarm bit is still set, the firmware honoured the clear but the **physical condition** that triggered it (e.g. a joint mashed against a limit) is still active - raise [`DobotAlarmError`](errors.md#dobotalarmerror) so the caller can address the physical condition. |
| `settle` | `float` | `0.15` | Verification settle delay in seconds. Only relevant when `verify=True`. |

**Returns.** `None`.

**Raises.** [`DobotAlarmError`](errors.md#dobotalarmerror) when `verify=True` and an alarm reasserts itself.

**Protocol.** [`CLEAR_ALL_ALARMS_STATE`](../protocol/command-ids.md) (20), **write** + immediate. Param: empty. Response: ack.

> **Note** - the protocol uses the same command ID (`20`) for read (get) and write (clear); the [`rw` bit](../protocol/ctrl-byte.md) of the control byte is what distinguishes them.

**Example - verify-on-clear.**

```python
from pydobotlab.errors import DobotAlarmError

try:
    bot.clear_alarm(verify=True)
except DobotAlarmError as e:
    print("alarm reasserted - fix the physical condition first:")
    for name in e.alarms:
        print("  •", name)
```

`clear_alarms()` (plural) is kept as a deprecated alias.

---

## `ensure_no_alarms() -> None`

**Purpose.** Guard call - raise [`DobotAlarmError`](errors.md#dobotalarmerror) if any alarm is currently active.

**Returns.** `None`.

**Protocol.** Sends `GET_ALARMS_STATE` (20) and inspects the result.

---

## `AlarmSet`

`from pydobotlab import AlarmSet`. The decoded result of `get_alarms()`.

| Attribute / Method            | Returns | What |
|-------------------------------|---------|------|
| `raw`                         | `bytes` | The original 16-byte mask, untouched. |
| `alarms`                      | `tuple[Alarm \| int, ...]` | Active alarm codes, named when known. |
| `bool(alarmset)`              | `bool`  | `True` iff any bit is set. |
| `iter(alarmset)`              | iter    | Iterates the active alarm codes. |
| `name in alarmset`            | `bool`  | Membership test. |
| `.names()`                    | `list[str]` | Friendly names, including categorised labels for unmapped codes (e.g. `JOINT_LIMIT_POS_0x44`). |
| `.format()`                   | `list[str]` | One `"{TAG}: {explanation + how to fix}"` line per active alarm - what the panel banner and `DobotKinematicError.message` use. |
| `.describe()`                 | `list[str]` | Backwards-compat alias for `.format()`. |

---

## `Alarm` codes

`from pydobotlab import Alarm`. The named bit positions in the mask. Categorised by byte:

| Byte | Range | Members |
|------|-------|---------|
| 0    | `0x00..0x07` | `PUBLIC_RESET`, `PUBLIC_UNDEFINED_INSTRUCTION`, `PUBLIC_FILE_SYSTEM`, `PUBLIC_MCU_COMM`, `PUBLIC_ANGLE_SENSOR_READ` |
| 2    | `0x10..0x17` | `PLAN_INVERSE_RESOLVE`, `PLAN_INVERSE_LIMIT`, `PLAN_DATA_REPEAT`, `PLAN_CURRENT_JOINT_OUT_OF_RANGE`, `PLAN_MOTION_TARGET_OUT_OF_WORKSPACE`, `PLAN_IN_SINGULARITY_ZONE` |
| 4    | `0x20..0x27` | `KINEMATIC_SINGULARITY`, `KINEMATIC_TARGET_OUT_OF_WORKSPACE`, `KINEMATIC_INVERSE_LIMIT` |
| 6    | `0x30..0x33` | `OVERSPEED_J1..J4` |
| 8    | `0x40..0x43` | `LIMIT_POS_J1..J4` (positive joint limit) |
| 10   | `0x50..0x53` | `LIMIT_NEG_J1..J4` (negative joint limit) |
| 12   | `0x60..0x63` | `LOST_STEP_J1..J4` |
| 14   | `0x70`       | `OTHER_LIMIT_TRIGGERED_J1_J2` (auto-leveling switch) |

Each named alarm has a one-line troubleshoot tip surfaced via `AlarmSet.format()`. For example, `LIMIT_POS_J3` reads:

> `joint 3 (forearm) hit positive limit - jog Z down (or J3 negative), or call set_home()`

Unmapped bits are surfaced as `JOINT_LIMIT_POS_0x44` / `OVERSPEED_0x35` / `UNKNOWN_0x90` etc. so they're never silently dropped.

---

## Recovery patterns

| Situation | What to do |
|-----------|-----------|
| Workspace / IK alarm (`PLAN_INVERSE_RESOLVE`, `PLAN_MOTION_TARGET_OUT_OF_WORKSPACE`, `KINEMATIC_*`) | The physical state is fine; the *target* was the problem. Call [`bot.clear_alarm()`](#clear-alarm), then retry with a reachable target. |
| Joint limit hit during JOG (`LIMIT_POS_J*` / `LIMIT_NEG_J*`) | The joint is *physically* against the stop. Jog away from the limit first, then `clear_alarm()`. Or just call [`bot.set_home()`](motion.md#set_home-waittrue-timeout600-raise_on_alarmtrue-int) - homing re-zeroes joints and clears the alarm in one step. |
| Lost step (`LOST_STEP_J*`) | Re-home to recalibrate. |
| Public / system fault (`PUBLIC_*`) | Power-cycle the arm (sometimes a re-home is enough for `PUBLIC_RESET`). |

The control panel's "Clear Alarm" button now calls [`clear_alarm()`](#clear-alarm) and re-polls 200 ms later; if the alarm comes back, it pops up an "Alarm persists" warning with the exact troubleshoot lines.
