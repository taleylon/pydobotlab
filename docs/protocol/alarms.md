# Alarm bitmask

`GET_ALARMS_STATE` (ID 20, get) returns a 16-byte (128-bit) bitmask. Each bit is an alarm code from `0x00` to `0x7F`. [`get_alarms`](../api/alarms.md#get_alarms) decodes the mask into an [`AlarmSet`](../api/alarms.md#alarmset).

## Bit layout

```
byte_index = code >> 3
bit_index  = code & 0x07
```

Alarm `0x42` (`LIMIT_POS_J3`) is `raw[8] & 0x04`.

## Code ranges

| Range | Category | Description |
|---|---|---|
| `0x00` to `0x07` | System | Reset, MCU communication, file system, sensor read errors. |
| `0x10` to `0x17` | Planning | Inverse-kinematics and planner failures. |
| `0x20` to `0x27` | Kinematics | Singularities, workspace, joint limits in inverse kinematics. |
| `0x30` to `0x37` | Overspeed | Per-joint overspeed. |
| `0x40` to `0x47` | Positive joint limit | Per-joint positive limit. |
| `0x50` to `0x57` | Negative joint limit | Per-joint negative limit. |
| `0x60` to `0x67` | Lost step | Per-joint lost-step result. |
| `0x70` to `0x77` | Other | Auto-leveling switch. |

The named codes are listed under [`Alarm`](../api/alarms.md#alarm).

## Exceptions

While an alarm is active, the arm does not run its queue. A command that waits for the arm, such as [`ptp`](../api/motion.md#ptp) or [`wait_for`](../api/queue.md#wait_for), raises a [`DobotAlarmError`](../api/errors.md#dobotalarmerror) subclass chosen by the alarm category, as listed under [`Alarm`](../api/alarms.md#alarm). System alarms (`0x00` to `0x07`) usually require a power cycle.

## Formatting

`AlarmSet.format()` returns one line per active alarm. The control panel banner and the message of `DobotAlarmError` use the same text.

```python
for line in bot.get_alarms().format():
    print(line)
```

```text
LIMIT_POS_J3: joint 3 (forearm) hit positive limit - jog Z down (or J3 negative), or call set_home()
```

## Encoding

`pydobotlab.alarms.encode_alarms` converts alarm codes back to a mask, for tests:

```python
from pydobotlab.alarms import Alarm, encode_alarms

encode_alarms([Alarm.LIMIT_POS_J3])
# b'\x00\x00\x00\x00\x00\x00\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00'
```
