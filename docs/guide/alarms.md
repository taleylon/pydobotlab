# Alarms and recovery

How to read alarms and recover from them. The methods are documented in [Alarms](../api/alarms.md) and the exceptions in [Exceptions](../api/errors.md). Examples assume a connected `Magician` named `bot`.

## Reading alarms

[`get_alarms`](../api/alarms.md#get_alarms) returns an [`AlarmSet`](../api/alarms.md#alarmset). Its `format()` method gives one line per alarm with a remedy.

```python
alarms = bot.get_alarms()
if alarms:
    for line in alarms.format():
        print(line)
```

## When an alarm occurs

While an alarm is active, the status LED of the arm is red and the arm does not move: a move queued during an alarm is dropped. The next command that waits for the arm, such as [`ptp`](../api/motion.md#ptp), raises a [`DobotAlarmError`](../api/errors.md#dobotalarmerror) subclass, which stops the program unless it is caught. Commands still queued are discarded, so clearing the alarm does not resume them. The control panel shows the active alarms in its banner.

Clear the alarm with [`clear_alarm`](../api/alarms.md#clear_alarm) or the Clear Alarm button of the panel. The LED turns green. A joint-limit alarm ends by itself when the joint is jogged back off the limit. [`set_home`](../api/motion.md#set_home) and the panel's Home button work also during an alarm: the arm homes, and the alarms are cleared when homing ends.

## Recovering from a failed move

```python
from pydobotlab import DobotAlarmError, DobotKinematicError

try:
    bot.ptp(mode=1, x=400, y=0, z=0, r=0)  # MOVJ_XYZ, outside the workspace
except DobotKinematicError as error:
    print(error)  # one line per alarm, with a remedy
    bot.clear_alarm()
except DobotAlarmError as error:
    print("alarms:", error.alarms)
    bot.clear_alarm()
```

How each alarm ends is listed under [`Alarm`](../api/alarms.md#alarm), and the exception for each code range under [Alarm groups](../api/alarms.md#alarm-groups).

## Recovery by alarm type

| Alarm | Recovery |
|---|---|
| Planning or motion (`PLAN_*`, `MOVE_*`) | Call `clear_alarm()`, then retry with a reachable target. |
| Joint or parallelogram limit (`LIMIT_*`) | Jog the joint back off the limit; the alarm ends by itself. |
| Overspeed (`OVERSPEED_J*`) | Lower `motion_params`, then call `clear_alarm()`. |
| Lost step (`LOST_STEP_J*`) | Call `set_home()`. |
| System (`PUBLIC_*`) | `PUBLIC_RESET` and `PUBLIC_UNDEFINED_INSTRUCTION`: call `clear_alarm()`. Others: power-cycle the arm. |

## Clearing

[`clear_alarm`](../api/alarms.md#clear_alarm) reads the alarms again after clearing. If the cause persists, for example a joint still pressed against its limit, the alarm becomes active again at once and stays active, and `clear_alarm` raises its exception. The Clear Alarm button of the panel shows the same message.

```python
try:
    bot.clear_alarm()
except DobotAlarmError as error:
    print("still active:", error.alarms)
```
