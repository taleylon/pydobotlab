# Motion

Read the arm pose and run point-to-point, continuous-path, and homing moves.

| Member | Description |
|---|---|
| [`Magician.get_pose`](#get_pose) | Read the current pose. |
| [`Magician.ptp`](#ptp) | Move to a target and wait until the move ends. |
| [`Magician.move_to`](#move_to) | Move to a Cartesian target and wait for completion. |
| [`Magician.set_r`](#set_r) | Rotate the end effector without moving X, Y, or Z. |
| [`Magician.set_home`](#set_home) | Move the arm to its home position. |
| [`Magician.cp`](#cp) | Queue a continuous-path segment. |
| [`Pose`](#pose) | Arm pose returned by `get_pose`. |
| [`PTPMode`](#ptpmode) | Point-to-point trajectory modes. |

Slideway moves are on the [Accessories](accessories.md#slideway) page.

---

## `Magician.get_pose` {#get_pose}

```python
Magician.get_pose() -> Pose
```

Read the current Cartesian position and joint angles.

**Returns** [`Pose`](#pose).

**Example**

```python
x, y, z, r, joints = bot.get_pose()
```

---

## `Magician.ptp` {#ptp}

```python
Magician.ptp(mode, x, y, z, r) -> bool
```

Move to a target in point-to-point mode and wait until the move ends.

Inside [`batch`](queue.md#batch), the move is queued and the method returns at once.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `mode` | [`PTPMode`](#ptpmode) or `int` | Trajectory mode, `0` to `9`. |
| `x`, `y`, `z`, `r` | `float` | Target. Cartesian position (mm) and rotation (degrees), joint angles (degrees), or increments, depending on `mode`. |

**Returns** `bool`: `True`.

**Raises**

- [`DobotKinematicError`](errors.md#dobotkinematicerror): the target is outside the [workspace](../guide/workspace.md), or a joint limit is hit.
- Another [`DobotAlarmError`](errors.md#dobotalarmerror) subclass: the arm reported another alarm.

**See also** [`move_to`](#move_to), [`batch`](queue.md#batch).

**Example**

```python
bot.ptp(mode=1, x=200, y=0, z=50, r=0)  # MOVJ_XYZ
bot.ptp(mode=2, x=200, y=50, z=50, r=0)  # MOVL_XYZ
```

---

## `Magician.move_to` {#move_to}

```python
Magician.move_to(x, y, z, r=0.0, *, mode=PTPMode.MOVJ_XYZ, wait=True, timeout=30.0, raise_on_alarm=True) -> int
```

Move to a Cartesian target in point-to-point mode.

Unlike [`ptp`](#ptp), it has a timeout, and with `wait=False` it returns the queue index at once for [`wait_for`](queue.md#wait_for).

**Parameters**

| Name | Type | Description |
|---|---|---|
| `x`, `y`, `z` | `float` | Target position, mm. |
| `r` | `float`, default `0.0` | End-effector rotation, degrees. |
| `mode` | [`PTPMode`](#ptpmode) or `int`, default `PTPMode.MOVJ_XYZ` | Trajectory mode. |
| `wait` | `bool`, default `True` | Block until the move executes. `False` returns after queuing. |
| `timeout` | `float` or `None`, default `30.0` | Maximum wait, seconds. `None` waits indefinitely. Applies when `wait=True`. |
| `raise_on_alarm` | `bool`, default `True` | Raise as soon as an alarm is active while waiting. |

**Returns** `int`: queue index of the move.

**Raises**

- [`DobotKinematicError`](errors.md#dobotkinematicerror): the target is out of reach, or a joint limit is hit.
- Another [`DobotAlarmError`](errors.md#dobotalarmerror) subclass: the arm reported another alarm.
- [`DobotTimeoutError`](errors.md#dobottimeouterror): `timeout` elapsed.

**See also** [`ptp`](#ptp), [`wait_for`](queue.md#wait_for), [`clear_alarm`](alarms.md#clear_alarm).

**Example**

```python
bot.move_to(200, 0, 50, mode=1)  # MOVJ_XYZ
bot.move_to(200, 50, 50, mode=2)  # MOVL_XYZ
```

---

## `Magician.set_r` {#set_r}

```python
Magician.set_r(r) -> bool
```

Rotate the end effector without moving X, Y, or Z, and wait until the rotation ends.

Reads the current pose, then moves to the same position with rotation `r` in `MOVJ_XYZ` mode.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `r` | `float` | Target rotation, degrees. |

**Returns** `bool`: `True`.

**Raises** [`DobotAlarmError`](errors.md#dobotalarmerror) subclass: the arm reported an alarm.

---

## `Magician.set_home` {#set_home}

```python
Magician.set_home() -> bool
```

Move the arm to its home position and wait until it arrives.

Works also during an alarm, as in DobotLab: the arm homes, and the alarms are cleared when homing ends.

**Returns** `bool`: `True`.

**Raises** [`DobotAlarmError`](errors.md#dobotalarmerror) subclass: an alarm comes back after clearing, as with [`clear_alarm`](alarms.md#clear_alarm).

---

## `Magician.cp` {#cp}

```python
Magician.cp(x, y, z, *, velocity=100.0, mode=1) -> int
```

Queue a continuous-path segment.

Consecutive segments are blended into one trajectory without stopping between them.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `x`, `y`, `z` | `float` | Target position, mm. |
| `velocity` | `float`, default `100.0` | Path velocity, mm/s. |
| `mode` | `int`, default `1` | `1` for an absolute target, `0` for a target relative to the current position. |

**Returns** `int`: queue index of the segment.

**See also** [`set_cp_params`](speed.md#set_cp_params), [`batch`](queue.md#batch), [Motion patterns](../guide/motion.md#continuous-path).

**Example**

```python
for x, y in [(200, 0), (220, 20), (240, 0)]:
    bot.cp(x, y, -40, velocity=80)
bot.wait_idle()
```

---

## `Pose` {#pose}

```python
class pydobotlab.Pose(x, y, z, r, j1, j2, j3, j4)
```

Arm pose returned by [`get_pose`](#get_pose). Immutable.

| Attribute | Type | Description |
|---|---|---|
| `x`, `y`, `z` | `float` | Cartesian position, mm. |
| `r` | `float` | End-effector rotation, degrees. |
| `j1`, `j2`, `j3`, `j4` | `float` | Joint angles, degrees. |
| `joints` | `list[float]` | `[j1, j2, j3, j4]`. |

| Method | Description |
|---|---|
| `as_xyzr()` | Return `(x, y, z, r)`. |
| `as_joints()` | Return `(j1, j2, j3, j4)`. |

Iterating a `Pose` yields `x`, `y`, `z`, `r`, and `joints`. `str(pose)` shows each value rounded to two decimals.

**Example**

```python
pose = bot.get_pose()
x, y, z, r = pose.as_xyzr()
```

---

## `PTPMode` {#ptpmode}

```python
class pydobotlab.PTPMode(IntEnum)
```

Point-to-point trajectory modes for [`ptp`](#ptp), [`move_to`](#move_to), and [`set_ptpwithl_cmd`](accessories.md#set_ptpwithl_cmd). Each method accepts a member or its value: `mode=PTPMode.MOVL_XYZ` and `mode=2` are equivalent.

| Member | Value | Target | Trajectory |
|---|---|---|---|
| `JUMP_XYZ` | 0 | Cartesian | Lift, travel, descend. |
| `MOVJ_XYZ` | 1 | Cartesian | Joint-interpolated. |
| `MOVL_XYZ` | 2 | Cartesian | Straight line. |
| `JUMP_ANGLE` | 3 | Joint angles | Lift, travel, descend. |
| `MOVJ_ANGLE` | 4 | Joint angles | Joint-interpolated. |
| `MOVL_ANGLE` | 5 | Joint angles | Linear in joint space. |
| `MOVJ_INC` | 6 | Joint increments | Joint-interpolated. |
| `MOVL_INC` | 7 | Cartesian increments | Straight line. |
| `MOVJ_XYZ_INC` | 8 | Cartesian increments | Joint-interpolated. |
| `JUMP_MOVL_XYZ` | 9 | Cartesian | Lift, straight-line travel, descend. |

JUMP lift height and Z limit are set with [`jump_params`](speed.md#jump_params).
