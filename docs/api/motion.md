# Pose & motion

Methods that read the current pose and queue trajectory motions (PTP - point-to-point - and HOME).

---

## `Pose`

`Pose` is the dataclass returned by [`get_pose()`](#get_pose). Frozen, slotted, iterable.

| Field | Type | Meaning |
|-------|------|---------|
| `x, y, z` | `float` | Cartesian position of the end-effector (mm). |
| `r` | `float` | End-effector rotation around the wrist (degrees). |
| `j1, j2, j3, j4` | `float` | Individual joint angles (degrees). |
| `joints` *(property)* | `list[float]` | `[j1, j2, j3, j4]`. |

Print a readable summary of the coordinates and joint angles:

```python
pose = bot.get_pose()
print(pose)
```

For example (illustrative values):

```text
Pose(x=220.00, y=0.00, z=50.00, r=0.00, joints=[0.00, 30.00, 45.00, 0.00])
```

`Pose.__str__` formats values to two decimal places for display. The attributes
retain their full precision. Positions are in millimetres; `r` and the joint
angles are in degrees.

Use `as_xyzr()` to unpack only the Cartesian coordinates, including rotation:

```python
x, y, z, r = pose.as_xyzr()
```

Iteration matches DobotLab's five-item return shape, with the joints as one list:

```python
x, y, z, r, joints = pose
```

Use `pose.as_joints()` for just the four joint angles as a tuple.

---

## `get_pose() -> Pose` {#get_pose}

**Purpose.** Read the current Cartesian + joint pose.

**Inputs.** None.

**Returns.** [`Pose`](#pose).

**Protocol.** [`GET_POSE`](../protocol/command-ids.md) (10), read-side, immediate. Response payload: 8 little-endian `float32` (`x, y, z, r, j1, j2, j3, j4`).

---

## `move_to(x, y, z, r=0.0, *, mode=PTPMode.MOVJ_XYZ, wait=True, timeout=30.0, raise_on_alarm=True) -> int` {#move-to}

**Purpose.** Queue a PTP move to a Cartesian target and (by default) block until it completes.

**Inputs.**

| Arg | Type | Default | Meaning |
|-----|------|---------|---------|
| `x, y, z` | `float` | – | Cartesian target (mm). |
| `r` | `float` | `0.0` | End-effector rotation (degrees). |
| `mode` | [`PTPMode`](#ptp-modes) | `MOVJ_XYZ` | How to interpolate the trajectory. |
| `wait` | `bool` | `True` | If `True`, block until the move runs. If `False`, return immediately. |
| `timeout` | `float \| None` | `30.0` | Seconds to wait before giving up (only relevant when `wait=True`). `None` = wait forever. |
| `raise_on_alarm` | `bool` | `True` | While waiting, raise [`DobotKinematicError`](errors.md#dobotkinematicerror-extends-dobotalarmerror) the moment a motion alarm fires (faster than waiting for the timeout). |

**Returns.** `int` - the queued-command index assigned by the firmware.

**Raises.**
* [`DobotKinematicError`](errors.md#dobotkinematicerror-extends-dobotalarmerror) - target outside the workspace, IK has no solution, or a joint limit is hit during the motion.
* [`DobotTimeoutError`](errors.md#dobottimeouterror) - `timeout` elapsed before the queue executed the command.

**Protocol.** [`SET_PTP_CMD`](../protocol/command-ids.md) (84), write + queued. Param layout: `u8 mode | float32 x | float32 y | float32 z | float32 r` (17 bytes). Response: `u64 queueIndex`.

**Example.**

```python
bot.move_to(200, 0, 50, 0)  # Cartesian, joint-interp.
bot.move_to(200, 0, 50, 0, mode=PTPMode.MOVL_XYZ)  # straight-line in Cartesian.
bot.move_to(200, 0, 50, 0, wait=False)  # fire-and-forget.
```

---

## `ptp(mode, x, y, z, r) -> int`

**Purpose.** Lower-level form of `move_to()` - queue a PTP move without the convenience wrapping (no waiting, no alarm-watching). Use this when you want to enqueue a sequence of moves and only wait at the end (often inside [`with bot.batch():`](queue.md#batch-context-manager)).

**Inputs.** `mode` (int or `PTPMode`), then `x, y, z, r` floats.

**Returns.** `int` queued-command index.

**Protocol.** Same as [`move_to`](#move-to) - [`SET_PTP_CMD`](../protocol/command-ids.md) (84).

---

## `set_home(*, wait=True, timeout=60.0, raise_on_alarm=True) -> int`

**Purpose.** Move the arm to its home position. The firmware does this in three internal stages (lift Z → swing base to home XY → descend), and re-zeroes any internal angle offsets along the way - which is why **`set_home()` also clears most alarms as a side-effect**.

**Inputs.**

| Arg | Type | Default | Meaning |
|-----|------|---------|---------|
| `wait` | `bool` | `True` | Block until home completes. |
| `timeout` | `float \| None` | `60.0` | Seconds to wait. Home is slow - keep this generous. |
| `raise_on_alarm` | `bool` | `True` | Raise on motion alarms while waiting. |

**Returns.** `int` queued-command index.

**Raises.**
* [`DobotKinematicError`](errors.md#dobotkinematicerror-extends-dobotalarmerror) - only fires if home itself is unreachable from the current pose (very unusual).
* [`DobotTimeoutError`](errors.md#dobottimeouterror) - home didn't finish in time.

**Protocol.** [`SET_HOME_CMD`](../protocol/command-ids.md) (31), write + queued. Param: `u32` (target XY mode, set to 0 in pydobotlab - fixed home). Response: `u64 queueIndex`.

**Note.** `home(...)` is kept as a deprecated alias.

---

## `set_r(r) -> int`

**Purpose.** Rotate the R axis (wrist) to `r` degrees without moving X/Y/Z.

**Inputs.** `r: float` - target wrist angle in degrees.

**Returns.** `int` queued-command index.

**Protocol.** [`SET_PTP_CMD`](../protocol/command-ids.md) (84) with `mode=MOVJ_XYZ` and current X/Y/Z. (We read the current pose first, then send a single-axis move.)

---

## `cp(x, y, z, *, velocity=100.0, mode=1) -> int`

**Purpose.** Queue one Continuous Path segment.

Unlike a chain of PTP `MOVL_XYZ` moves, the firmware does **not** decelerate to zero between consecutive `cp()` calls - it blends them into a single smooth trajectory. This is the right tool for drawing, engraving, and any path where the small visible pauses of PTP-MOVL at every waypoint are undesirable.

**Inputs.**

| Arg | Type | Default | Meaning |
|-----|------|---------|---------|
| `x, y, z` | `float` | – | Cartesian target (mm). |
| `velocity` | `float` | `100.0` | Path velocity (mm/s). |
| `mode` | `int` | `1` | `1` = absolute, `0` = relative. |

**Returns.** `int` queued-command index.

**Protocol.** [`SET_CP_CMD`](../protocol/command-ids.md) (91), write + queued. Param: `u8 cpMode | f32 x | f32 y | f32 z | f32 velocity` (17 bytes).

**Notes.** Call [`set_cp_params`](speed.md#set_cp_paramsplan_acc-junction_vel-acc00-real_time_trackfalse-int) once at the start of your program to tune corner smoothness. Without it, the firmware uses a conservative default and corners look rounded.

**Example - drawing a circle with no per-segment pause:**

```python
import math

bot.set_cp_params(plan_acc=200.0, junction_vel=200.0, acc=200.0)
with bot.batch():
    bot.ptp(PTPMode.MOVL_XYZ, 200, 0, -45, 0)  # pen down at start
    for i in range(64):
        a = 2 * math.pi * i / 64
        bot.cp(200 + 30 * math.cos(a), 30 * math.sin(a), -45, velocity=80)
bot.wait_idle()
```

See `examples/draw_smiley.py` for a complete eager-vs-lazy-vs-continuous comparison.

---

## `set_ptpwithl_cmd(mode, x, y, z, r, l) -> int`

**Purpose.** PTP move that *also* drives the slideway (the optional linear rail) to position `l` (mm).

**Inputs.**

| Arg | Type | Meaning |
|-----|------|---------|
| `mode` | `int / PTPMode` | Same modes as `ptp()`. |
| `x, y, z, r` | `float` | Arm target. |
| `l` | `float` | Slideway target (mm). |

**Returns.** `int` queued-command index.

**Protocol.** [`SET_PTP_WITH_L_CMD`](../protocol/command-ids.md) (86), write + queued. Param: `u8 mode | float32 x | float32 y | float32 z | float32 r | float32 l` (21 bytes).

**Note.** Requires the slideway to be enabled with [`set_device_withl(True, version=...)`](extras.md#set_device_withlenable-version0-int).

---

## `get_posel() -> float`

**Purpose.** Slideway position in millimetres.

**Returns.** `float`.

**Protocol.** [`GET_POSE_L`](../protocol/command-ids.md) (13), read, immediate.

`get_pose_l()` and `get_slideway_pose()` are kept as deprecated aliases.

---

## PTP modes

The `PTPMode` enum (`from pydobotlab import PTPMode`) selects how the firmware interpolates the trajectory:

| Member         | Value | Target frame | Trajectory |
|----------------|-------|--------------|------------|
| `JUMP_XYZ`     | 0     | Cartesian    | Lift up to JUMP height, fly across, drop down - pick-and-place style. |
| `MOVJ_XYZ`     | 1     | Cartesian    | Joint-interpolated (smooth in joint space, curved in Cartesian). |
| `MOVL_XYZ`     | 2     | Cartesian    | Linear in Cartesian (straight line). |
| `JUMP_ANGLE`   | 3     | Joint        | Same as `JUMP_XYZ` but target is `j1..j4`. |
| `MOVJ_ANGLE`   | 4     | Joint        | Joint-interpolated to joint targets. |
| `MOVL_ANGLE`   | 5     | Joint        | Linear-in-joint-space to joint targets. |
| `MOVJ_INC`     | 6     | Joint Δ      | Relative joint move (`Δj1..Δj4`). |
| `MOVL_INC`     | 7     | Cartesian Δ  | Relative linear Cartesian move. |
| `MOVJ_XYZ_INC` | 8     | Cartesian Δ  | Relative Cartesian joint-interp move. |

JUMP heights and the in-flight Z limit are configured via [`bot.jump_params`](speed.md#jump_params-property-tuplefloat-float).
