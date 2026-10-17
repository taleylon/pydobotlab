# Alarm bitmask

`GET_ALARMS_STATE` (ID 20, get) returns a 16-byte (128-bit) bitmask. Each bit is an alarm code from `0x00` to `0x7F`. [`get_alarms`](../api/alarms.md#get_alarms) decodes the mask into an [`AlarmSet`](../api/alarms.md#alarmset). The codes are defined in the [Dobot Magician ALARM Description](../Dobot-Magician-ALARM-Description.pdf) V1.0.1.

## Bit layout

```
byte_index = code >> 3
bit_index  = code & 0x07
```

Alarm `0x44` (`LIMIT_POS_J3`) is `raw[8] & 0x10`.

Example from the ALARM Description: the mask `01 00 00 00 00 00 00 00 08 00 00 00 00 00 00 00` has bits 0 and 67 set, that is `0x00` (`PUBLIC_RESET`) and `0x43` (`LIMIT_NEG_J2`).

## Code ranges

| Range | Group | Description |
|---|---|---|
| `0x00` to `0x0F` | System | Reset, unknown command, file system, MCU-FPGA communication, angle sensor. |
| `0x10` to `0x1F` | Planning | The target of a command cannot be reached. |
| `0x20` to `0x2F` | Motion | The path of a running move cannot be followed. |
| `0x30` to `0x3F` | Overspeed | Per-joint overspeed. |
| `0x40` to `0x4F` | Limit | Per-joint positive and negative limits, and the parallelogram limits. |
| `0x50` to `0x5F` | Lost step | Per-joint lost step. |

The named codes are listed under [`Alarm`](../api/alarms.md#alarm).

## Exceptions

A command that waits for the arm, such as [`ptp`](../api/motion.md#ptp) or [`wait_for`](../api/queue.md#wait_for), raises a [`DobotAlarmError`](../api/errors.md#dobotalarmerror) subclass chosen by the alarm group, as listed under [Alarm groups](../api/alarms.md#alarm-groups). A move queued while an alarm is active is dropped. [`set_home`](../api/motion.md#set_home) homes also during an alarm.

## Formatting

`AlarmSet.format()` returns one line per active alarm. The message of `DobotAlarmError` uses the same text.

```python
for line in bot.get_alarms().format():
    print(line)
```

```text
LIMIT_POS_J3: joint 3 (forearm) at its positive limit - jog J3 negative
```

## Encoding

`pydobotlab.alarms.encode_alarms` converts alarm codes back to a mask, for tests:

```python
from pydobotlab.alarms import Alarm, encode_alarms

encode_alarms([Alarm.LIMIT_POS_J3])
# b'\x00\x00\x00\x00\x00\x00\x00\x00\x10\x00\x00\x00\x00\x00\x00\x00'
```
