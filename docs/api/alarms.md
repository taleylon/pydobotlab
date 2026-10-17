# Alarms

Read, check, and clear alarms reported by the arm.

| Member | Description |
|---|---|
| [`Magician.get_alarms`](#get_alarms) | Read the active alarms. |
| [`Magician.clear_alarm`](#clear_alarm) | Clear all active alarms and confirm that none comes back. |
| [`Magician.ensure_no_alarms`](#ensure_no_alarms) | Raise if any alarm is active. |
| [`AlarmSet`](#alarmset) | Decoded alarm state. |
| [`Alarm`](#alarm) | Alarm codes. |
| [Alarm groups](#alarm-groups) | Code ranges and their exceptions. |

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
| `names()` | Return the names of the active alarms as `list[str]`. Unnamed codes are labeled by group and code, for example `LIMIT_0x4A`. |
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

Alarm codes, as defined in the [Dobot Magician ALARM Description](../Dobot-Magician-ALARM-Description.pdf) V1.0.1. Each value is the bit position in the 128-bit alarm bitmask.

| Code | Member | Meaning | Ends when |
|---|---|---|---|
| `0x00` | `PUBLIC_RESET` | The arm was reset. | Cleared. |
| `0x01` | `PUBLIC_UNDEFINED_INSTRUCTION` | An unknown command was received. | Cleared. |
| `0x02` | `PUBLIC_FILE_SYSTEM` | File system error. | The arm is reset successfully. |
| `0x03` | `PUBLIC_MCU_COMM` | MCU-FPGA communication failed at start-up. | The arm is reset successfully. |
| `0x04` | `PUBLIC_ANGLE_SENSOR_READ` | An angle sensor gave a wrong value. | The arm is power-cycled. |
| `0x10` | `PLAN_INVERSE_SINGULARITY` | The target is in an abnormal position. | Cleared. |
| `0x11` | `PLAN_INVERSE_CALCULATION` | The target is out of the workspace. | Cleared. |
| `0x12` | `PLAN_INVERSE_LIMIT` | The target needs a joint beyond its limit: J1 -90° to 90°, J2 0° to 85°, J3 -10° to 90°, J4 -90° to 90°. | Cleared. |
| `0x13` | `PLAN_DATA_REPEAT` | Repeated points in an ARC or JUMP_MOVL move. | Cleared. |
| `0x14` | `PLAN_ARC_INPUT_PARAMETER` | Invalid ARC points. | Cleared. |
| `0x15` | `PLAN_JUMP_PARAMETER` | Invalid JUMP parameters, such as a negative height. | Cleared. |
| `0x20` | `MOVE_INVERSE_SINGULARITY` | The path passes a singular pose. | Cleared. |
| `0x21` | `MOVE_INVERSE_CALCULATION` | The path leaves the workspace. | Cleared. |
| `0x22` | `MOVE_INVERSE_LIMIT` | The path needs a joint beyond its limit. | Cleared. |
| `0x30` to `0x33` | `OVERSPEED_J1` to `OVERSPEED_J4` | A joint exceeded its maximum speed. | Cleared. |
| `0x40` to `0x47` | `LIMIT_POS_J1`, `LIMIT_NEG_J1`, ..., `LIMIT_POS_J4`, `LIMIT_NEG_J4` | A joint reached its positive or negative limit. | The joint is jogged back. |
| `0x48`, `0x49` | `LIMIT_POS_PARALLELOGRAM`, `LIMIT_NEG_PARALLELOGRAM` | The rear arm and forearm are stretched or folded to their limit. | The arm leaves the limit. |
| `0x50` to `0x53` | `LOST_STEP_J1` to `LOST_STEP_J4` | A joint lost steps. | The arm is homed. |

"Cleared" means [`clear_alarm`](#clear_alarm) or the Clear Alarm button of the panel. The exception for each code is listed under [Alarm groups](#alarm-groups). The bitmask layout is described in [Alarm bitmask](../protocol/alarms.md).

---

## Alarm groups {#alarm-groups}

| Codes | Group | Exception |
|---|---|---|
| `0x00` to `0x0F` | System | [`DobotSystemAlarmError`](errors.md#dobotsystemalarmerror) |
| `0x10` to `0x1F` | Planning | [`DobotKinematicError`](errors.md#dobotkinematicerror) |
| `0x20` to `0x2F` | Motion | [`DobotKinematicError`](errors.md#dobotkinematicerror) |
| `0x30` to `0x3F` | Overspeed | [`DobotOverspeedError`](errors.md#dobotoverspeederror) |
| `0x40` to `0x4F` | Limit | [`DobotKinematicError`](errors.md#dobotkinematicerror) |
| `0x50` to `0x5F` | Lost step | [`DobotLostStepError`](errors.md#dobotloststeperror) |
| `0x60` to `0x7F` | Not defined | [`DobotAlarmError`](errors.md#dobotalarmerror) |

When several alarms are active, the exception follows the alarm with the lowest code.
