# Hello, Magician

A first program that homes the arm, moves it, and reads its pose. Start the control panel with `pydobotlab-panel` first; the program connects through it.

```python
from pydobotlab import Magician

with Magician() as bot:
    bot.set_home()

    # Move to x=200, y=0, z=50 mm with rotation 0 degrees.
    bot.ptp(mode=1, x=200, y=0, z=50, r=0)

    pose = bot.get_pose()
    print(f"x={pose.x:.1f}  y={pose.y:.1f}  z={pose.z:.1f}  r={pose.r:.1f}")
    print(f"joints: {pose.joints}")

    bot.ptp(mode=1, x=150, y=120, z=50, r=0)
    bot.ptp(mode=1, x=150, y=-120, z=50, r=0)

    bot.set_home()
```

- `with Magician() as bot:` connects on entry and disconnects on exit, including when an exception is raised.
- `set_home` returns when the arm has homed, and [`ptp`](../api/motion.md#ptp) returns when the move has ended. Each command starts after the previous one.
- `mode=1` is `MOVJ_XYZ`, a joint-interpolated move to a Cartesian target. See [`PTPMode`](../api/motion.md#ptpmode) for all modes.
- `get_pose` returns a [`Pose`](../api/motion.md#pose) with the attributes `x`, `y`, `z`, `r`, and `joints`. It also unpacks as `x, y, z, r, joints`.

## Suction cup

```python
with Magician() as bot:
    bot.set_home()
    bot.jump_params = 150, 30  # zlimit 150 mm, lift height 30 mm

    bot.ptp(mode=0, x=200, y=80, z=-30, r=0)
    bot.set_endeffector_suctioncup(enable=True, on=True)  # pick
    bot.ptp(mode=0, x=200, y=-80, z=-30, r=0)
    bot.set_endeffector_suctioncup(enable=True, on=False)  # release

    bot.set_home()
```

`mode=0` is `JUMP_XYZ`: the arm lifts, travels, and descends in one command. The lift height and Z limit are set by [`jump_params`](../api/speed.md#jump_params).

`enable` powers the end effector and `on` applies suction. [`set_endeffector_gripper`](../api/end-effectors.md#set_endeffector_gripper) takes the same arguments.

## Handling errors

When the arm reports an alarm, the command raises an exception and the program stops. For an unreachable target or a joint limit, `ptp` raises [`DobotKinematicError`](../api/errors.md#dobotkinematicerror). The message lists each alarm with a remedy. The arm refuses further commands until the alarm is cleared.

```python
from pydobotlab import Magician
from pydobotlab.errors import DobotKinematicError

with Magician() as bot:
    try:
        bot.ptp(mode=1, x=9999, y=0, z=0, r=0)  # outside the workspace
    except DobotKinematicError as error:
        print(error)
        bot.clear_alarm()
```

See [Workspace](../guide/workspace.md), [Alarms and recovery](../guide/alarms.md), and [Exceptions](../api/errors.md).

## Next

- [Running without hardware](simulator.md)
- [API reference](../api/overview.md)
