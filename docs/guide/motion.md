# Motion patterns

Common combinations of the [motion](../api/motion.md), [queue](../api/queue.md), and [end-effector](../api/end-effectors.md) methods. Examples assume a connected `Magician` named `bot`.

## Moves

[`ptp`](../api/motion.md#ptp) returns when the move has ended, so the next line runs with the arm at the target. The other DobotLab functions, such as the end-effector and I/O commands, also wait until the arm has executed them.

```python
bot.ptp(mode=1, x=200, y=0, z=50, r=0)
bot.ptp(mode=2, x=200, y=50, z=50, r=0)
print(bot.get_pose())
```

`mode=1` is `MOVJ_XYZ`, a joint-interpolated move to a Cartesian target. `mode=2` is `MOVL_XYZ`, a straight-line move. See [`PTPMode`](../api/motion.md#ptpmode) for all modes.

## Queuing a sequence

Inside [`batch`](../api/queue.md#batch), commands are only queued. When the block exits, the arm runs the whole sequence without waiting for Python between moves, and the block waits until it ends.

```python
with bot.batch():
    for x, y in points:
        bot.ptp(mode=2, x=x, y=y, z=0, r=0)
```

## Continuous path

Consecutive `MOVL_XYZ` moves decelerate to a stop at each waypoint. [`cp`](../api/motion.md#cp) segments are blended into one trajectory, which suits drawing and engraving. Set the corner behavior once with [`set_cp_params`](../api/speed.md#set_cp_params).

```python
import math

bot.set_cp_params(plan_acc=200, junction_vel=200, acc=200)
with bot.batch():
    bot.ptp(mode=2, x=230, y=0, z=-45, r=0)  # move to the start point
    for i in range(65):
        angle = 2 * math.pi * i / 64
        bot.cp(200 + 30 * math.cos(angle), 30 * math.sin(angle), -45, velocity=80)
```

`examples/draw_smiley.py` compares point-to-point, batched, and continuous-path drawing.

## Pick and place

```python
bot.set_home()
bot.ptp(mode=1, x=200, y=80, z=60, r=0)  # above the pick point
bot.ptp(mode=1, x=200, y=80, z=-30, r=0)
bot.set_endeffector_suctioncup(enable=True, on=True)  # pick
bot.ptp(mode=1, x=200, y=80, z=60, r=0)
bot.ptp(mode=1, x=200, y=-80, z=60, r=0)  # above the place point
bot.ptp(mode=1, x=200, y=-80, z=-30, r=0)
bot.set_endeffector_suctioncup(enable=True, on=False)  # release
bot.ptp(mode=1, x=200, y=-80, z=60, r=0)
```

All moves use `mode=1` (`MOVJ_XYZ`). Each command starts after the previous one has ended.

A `JUMP_XYZ` move (`mode=0`) lifts, travels, and descends in one command. The lift height and Z limit come from [`jump_params`](../api/speed.md#jump_params).

```python
bot.jump_params = 150, 30  # zlimit 150 mm, lift 30 mm
bot.ptp(mode=0, x=200, y=80, z=-30, r=0)
```

## Speed

Velocity ratios scale the full-speed values of the firmware:

| Motion | 100 % velocity |
|---|---|
| Point-to-point ([`motion_params`](../api/speed.md#motion_params)) | 200 mm/s |
| Jogging X, Y, Z ([`set_jog_common_params`](../api/speed.md#set_jog_common_params)) | 200 mm/s |
| Jogging R and joints | 90 °/s |

For example, `bot.motion_params = 50, 50` moves at about 100 mm/s.
