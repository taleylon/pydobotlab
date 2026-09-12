# Alarm bitmask

`GET_ALARMS_STATE` (cmd 20, read) returns 16 raw bytes — a 128-bit alarm bitmask. Each bit is a named alarm code from `0x00` to `0x7F`. pydobotlab decodes this into an [`AlarmSet`](../api/alarms.md#alarmset).

## Bit layout

```
bit position  =  byte_index * 8 + bit_within_byte
                 ─────────       ────────────────
                 raw[0..15]      bit_within_byte = code & 0x07
                                 byte_index      = code >> 3
```

So alarm `0x42` (LIMIT_POS_J3) lives in `raw[8]`, bit 2 (i.e. `raw[8] & 0x04`).

## Code ranges

| Range          | Category        | Comments |
|----------------|-----------------|----------|
| `0x00..0x07`   | System / Public | Reset, MCU comms, file system, sensor read errors. |
| `0x10..0x17`   | Plan            | IK / planner failures. |
| `0x20..0x27`   | Kinematic       | Singularities, workspace, IK joint-limit. |
| `0x30..0x37`   | Overspeed       | Per-joint overspeed (`OVERSPEED_J1..J4`). |
| `0x40..0x47`   | Joint limit, positive | Per-joint hard positive limit. |
| `0x50..0x57`   | Joint limit, negative | Per-joint hard negative limit. |
| `0x60..0x67`   | Lost step       | Per-joint lost-step detection result. |
| `0x70..0x77`   | Other           | Auto-leveling switch, etc. |

A complete enumeration of named codes is on the [Alarms](../api/alarms.md#alarm-codes) API page.

## Why pydobotlab raises on motion alarms

Codes `0x10..0x77` (i.e. plan / kinematic / overspeed / joint-limit / lost-step / other) are **motion-related**. When any of these fire while a motion is pending, pydobotlab raises [`DobotKinematicError`](../api/errors.md#dobotkinematicerror-extends-dobotalarmerror) from the waiters ([`move_to`](../api/motion.md#move-to), [`set_home`](../api/motion.md#set_home-waittrue-timeout600-raise_on_alarmtrue-int), [`wait_for`](../api/queue.md#wait_forindex-timeoutnone-poll002-raise_on_alarmtrue-none), [`wait_idle`](../api/queue.md#wait_idle-timeoutnone-poll002-raise_on_alarmtrue-none)) instead of waiting forever for a queued command the firmware has refused to execute.

Codes `0x00..0x07` (system) typically need a power-cycle, not just `clear_alarm()`. pydobotlab does *not* automatically raise on these — they're informational.

## Pretty-printing

```python
mask = bot.get_alarms()
if mask:
    for line in mask.format():
        print(" •", line)
```

Sample output (for `LIMIT_POS_J3`):

```
 • LIMIT_POS_J3: joint 3 (forearm) hit positive limit — jog Z down (or J3 negative), or call set_home()
```

The `format()` output is what the panel banner displays and what `DobotKinematicError`'s message contains.

## Encoding back (mostly for tests)

```python
from pydobotlab.alarms import Alarm, encode_alarms

encode_alarms(
    [Alarm.LIMIT_POS_J3]
)  # → b'\x00\x00\x00\x00\x00\x00\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00'
```
