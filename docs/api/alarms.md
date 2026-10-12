# Alarms

Read, check, and clear alarms reported by the arm.

| Member | Description |
|---|---|
| [`Magician.get_alarms`](#get_alarms) | Read the active alarms. |
| [`Magician.clear_alarm`](#clear_alarm) | Clear all active alarms and confirm that none comes back. |
| [`Magician.ensure_no_alarms`](#ensure_no_alarms) | Raise if any alarm is active. |
| [`AlarmSet`](#alarmset) | Decoded alarm state. |
| [`Alarm`](#alarm) | Alarm codes. |

Recovery procedures are described in [Alarms and recovery](../guide/alarms.md).

---

## `Magician.get_alarms` {#get_alarms}

```python
Magician.get_alarms() -> AlarmSet
```

Read the active alarms.

**Returns** [`AlarmSet`](#alarmset).

**Example**

```python
for line in bot.get_alarms().format():
    print(line)
```

---

## `Magician.clear_alarm` {#clear_alarm}

```python
Magician.clear_alarm() -> bool
```

Clear all active alarms and confirm that none comes back.

After clearing, waits 0.2 seconds and reads the alarms again. An alarm whose cause is still present, for example a joint against its limit, becomes active again at once and stays active.

**Returns** `bool`: `True`.

**Raises** [`DobotAlarmError`](errors.md#dobotalarmerror) subclass: an alarm is active again after clearing.

---

## `Magician.ensure_no_alarms` {#ensure_no_alarms}

```python
Magician.ensure_no_alarms() -> None
```

Raise if any alarm is active.

**Raises**

- [`DobotAlarmError`](errors.md#dobotalarmerror) subclass: at least one alarm is active. Its `alarms` attribute lists the alarm names.

---

## `AlarmSet` {#alarmset}

```python
class pydobotlab.AlarmSet(raw, alarms)
```

Decoded alarm state returned by [`get_alarms`](#get_alarms). Immutable.

| Attribute | Type | Description |
|---|---|---|
| `raw` | `bytes` | 16-byte alarm bitmask. |
| `alarms` | `tuple` of `Alarm` or `int` | Active alarm codes. Codes without a name are `int`. |

| Method | Description |
|---|---|
| `names()` | Return the names of the active alarms as `list[str]`. Unnamed codes are labeled by range, for example `JOINT_LIMIT_POS_0x44`. |
| `format()` | Return one `"NAME: remedy"` line per active alarm as `list[str]`. |

`bool(alarm_set)` is `True` when any alarm is active. Iterating yields the codes in `alarms`. `code in alarm_set` tests whether an alarm is active.

**Example**

```python
alarms = bot.get_alarms()
if Alarm.LIMIT_POS_J3 in alarms:
    print(alarms.names())
```

---

## `Alarm` {#alarm}

```python
class pydobotlab.Alarm(IntEnum)
```

Alarm codes. Each value is the bit position in the 128-bit alarm bitmask.

| Codes | Category | Members | Exception |
|---|---|---|---|
| `0x00` to `0x04` | System | `PUBLIC_RESET`, `PUBLIC_UNDEFINED_INSTRUCTION`, `PUBLIC_FILE_SYSTEM`, `PUBLIC_MCU_COMM`, `PUBLIC_ANGLE_SENSOR_READ` | [`DobotSystemAlarmError`](errors.md#dobotsystemalarmerror) |
| `0x10` to `0x15` | Planning | `PLAN_INVERSE_RESOLVE`, `PLAN_INVERSE_LIMIT`, `PLAN_DATA_REPEAT`, `PLAN_CURRENT_JOINT_OUT_OF_RANGE`, `PLAN_MOTION_TARGET_OUT_OF_WORKSPACE`, `PLAN_IN_SINGULARITY_ZONE` | [`DobotKinematicError`](errors.md#dobotkinematicerror) |
| `0x20` to `0x22` | Kinematics | `KINEMATIC_SINGULARITY`, `KINEMATIC_TARGET_OUT_OF_WORKSPACE`, `KINEMATIC_INVERSE_LIMIT` | [`DobotKinematicError`](errors.md#dobotkinematicerror) |
| `0x30` to `0x33` | Overspeed | `OVERSPEED_J1` to `OVERSPEED_J4` | [`DobotOverspeedError`](errors.md#dobotoverspeederror) |
| `0x40` to `0x43` | Positive joint limit | `LIMIT_POS_J1` to `LIMIT_POS_J4` | [`DobotKinematicError`](errors.md#dobotkinematicerror) |
| `0x50` to `0x53` | Negative joint limit | `LIMIT_NEG_J1` to `LIMIT_NEG_J4` | [`DobotKinematicError`](errors.md#dobotkinematicerror) |
| `0x60` to `0x63` | Lost step | `LOST_STEP_J1` to `LOST_STEP_J4` | [`DobotLostStepError`](errors.md#dobotloststeperror) |
| `0x70` | Other | `OTHER_LIMIT_TRIGGERED_J1_J2` | [`DobotAlarmError`](errors.md#dobotalarmerror) |

When several alarms are active, the exception follows the alarm with the lowest code. The bitmask layout is described in [Alarm bitmask](../protocol/alarms.md).
