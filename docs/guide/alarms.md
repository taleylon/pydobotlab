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

While an alarm is active, the status LED of the arm is red and the arm does not execute commands. The next command that waits for the arm, such as [`ptp`](../api/motion.md#ptp), raises a [`DobotAlarmError`](../api/errors.md#dobotalarmerror) subclass, which stops the program unless it is caught. Commands still queued are discarded, so clearing the alarm does not resume them. The control panel shows the active alarms in its banner.

Clear the alarm with [`clear_alarm`](../api/alarms.md#clear_alarm) or the Clear Alarm button of the panel. The LED turns green.

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

The exception for each alarm category is listed under [`Alarm`](../api/alarms.md#alarm).

## Recovery by alarm type

| Alarm | Recovery |
|---|---|
| Planning or kinematics (`PLAN_*`, `KINEMATIC_*`) | Call `clear_alarm()`, then retry with a reachable target. |
| Joint limit (`LIMIT_POS_J*`, `LIMIT_NEG_J*`) | Jog the joint away from the limit, then call `clear_alarm()`. |
| Overspeed (`OVERSPEED_J*`) | Lower `motion_params`, then call `clear_alarm()`. |
| Lost step (`LOST_STEP_J*`) | Call `clear_alarm()`, then `set_home()`. |
| System (`PUBLIC_*`) | Power-cycle the arm. |

## Clearing

[`clear_alarm`](../api/alarms.md#clear_alarm) reads the alarms again after clearing. If the cause persists, for example a joint still pressed against its limit, the alarm becomes active again at once and stays active, and `clear_alarm` raises its exception. The Clear Alarm button of the panel shows the same message.

```python
try:
    bot.clear_alarm()
except DobotAlarmError as error:
    print("still active:", error.alarms)
```
