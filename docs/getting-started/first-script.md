# Hello, Magician

Your first program: home the arm, move to a couple of points, and read back the pose.

```python
from pydobotlab import Magician

with Magician() as bot:
    # 1. Send the arm to its home position. Blocks until done.
    bot.set_home()

    # 2. Move to (200, 0, 50) mm with the end-effector pointing at R = 0°.
    #    Cartesian, joint-interpolated. Blocks by default.
    bot.move_to(200, 0, 50, 0)

    # 3. Read the current pose and print it.
    pose = bot.get_pose()
    print(f"x={pose.x:.1f}  y={pose.y:.1f}  z={pose.z:.1f}  r={pose.r:.1f}")
    print(f"joints: {pose.joints}")

    # 4. Swing left, then right.
    bot.move_to(150, 120, 50, 0)
    bot.move_to(150, -120, 50, 0)

    # 5. Back to home.
    bot.set_home()
```

Things to notice:

* `with Magician() as bot:` opens the port on entry and closes it on exit (so you don't leak the serial device if your script crashes).
* `set_home()` and `move_to()` **block** until the firmware has executed them. Pass `wait=False` if you want to fire-and-forget.
* `get_pose()` returns a [`Pose`](../api/motion.md#pose) — namedtuple-like, accessible by `.x .y .z .r` *and* by index, with a `.joints` property for the four joint angles.

## Adding the suction cup

```python
with Magician() as bot:
    bot.set_home()
    bot.move_to(200, 80, -30, 0)
    bot.set_endeffector_suctioncup(enable=True, on=True)  # pick up
    bot.move_to(200, 80, 60, 0)
    bot.move_to(200, -80, 60, 0)
    bot.move_to(200, -80, -30, 0)
    bot.set_endeffector_suctioncup(enable=True, on=False)  # release
    bot.set_home()
```

`enable` activates the cup (mounts it as the active end-effector); `on` opens or closes the valve. Same shape for [`set_endeffector_gripper()`](../api/end-effectors.md#set_endeffector_gripperenable-on-int).

## Catching mistakes

`move_to()` raises [`DobotKinematicError`](../api/errors.md#dobotkinematicerror-extends-dobotalarmerror) if the target is unreachable, the IK has no solution, or a joint limit is hit during the motion. The exception message includes a per-alarm troubleshoot line so you know what to fix and how:

```python
from pydobotlab import Magician
from pydobotlab.errors import DobotKinematicError

with Magician() as bot:
    try:
        bot.move_to(9999, 0, 0, 0)  # way outside reach
    except DobotKinematicError as e:
        print(e)
        bot.clear_alarm()  # back to a clean state
```

See [Alarms](../api/alarms.md) and [Errors & exceptions](../api/errors.md) for the full picture.

## Next

* [Running without hardware (simulator) →](simulator.md)
* [API Reference overview →](../api/overview.md)
