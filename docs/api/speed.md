# Motion parameters

Set and read velocity, acceleration, JUMP, and continuous-path parameters.

| Member | Description |
|---|---|
| [`Magician.motion_params`](#motion_params) | Point-to-point velocity and acceleration ratios. |
| [`Magician.jump_params`](#jump_params) | JUMP Z limit and lift height. |
| [`Magician.set_jog_common_params`](#set_jog_common_params) | Set jog velocity and acceleration ratios. |
| [`Magician.get_jog_common_params`](#get_jog_common_params) | Read jog velocity and acceleration ratios. |
| [`Magician.get_arm_speed_ratio`](#get_arm_speed_ratio) | Read the jog or point-to-point velocity ratio. |
| [`Magician.set_cp_params`](#set_cp_params) | Set continuous-path planning parameters. |

Slideway velocity is set with [`set_ptpl_params`](accessories.md#set_ptpl_params).

---

## `Magician.motion_params` {#motion_params}

```python
Magician.motion_params: tuple[float, float]
```

Velocity and acceleration ratios for point-to-point moves, in percent.

Reading returns `(velocity, acceleration)`. Assigning a pair sets the new values and waits until the arm applies them; inside [`batch`](queue.md#batch), the values are queued. Assigning raises a [`DobotAlarmError`](errors.md#dobotalarmerror) subclass if the arm reports an alarm.

**Example**

```python
bot.motion_params = 50, 50
velocity, acceleration = bot.motion_params
```

---

## `Magician.jump_params` {#jump_params}

```python
Magician.jump_params: tuple[float, float]
```

Parameters of `JUMP` point-to-point moves, as `(zlimit, height)`.

| Element | Description |
|---|---|
| `zlimit` | Maximum Z of the trajectory, mm. |
| `height` | Lift height above the higher endpoint, mm. |

Reading returns `(zlimit, height)`. Assigning a pair sets the new values in the same way as [`motion_params`](#motion_params).

**Example**

```python
bot.jump_params = 150, 30
```

---

## `Magician.set_jog_common_params` {#set_jog_common_params}

```python
Magician.set_jog_common_params(vel_ratio, acc_ratio) -> int
```

Set the velocity and acceleration ratios for jogging.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `vel_ratio` | `float` | Velocity ratio, percent. |
| `acc_ratio` | `float` | Acceleration ratio, percent. |

**Returns** `int`: queue index of the command.

---

## `Magician.get_jog_common_params` {#get_jog_common_params}

```python
Magician.get_jog_common_params() -> tuple[float, float]
```

Read the velocity and acceleration ratios for jogging.

**Returns** `tuple[float, float]`: `(vel_ratio, acc_ratio)`, in percent.

---

## `Magician.get_arm_speed_ratio` {#get_arm_speed_ratio}

```python
Magician.get_arm_speed_ratio(mode) -> float
```

Read the velocity ratio for jogging or point-to-point moves.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `mode` | `int` | `0` for jogging, `1` for point-to-point moves. |

**Returns** `float`: velocity ratio, percent.

---

## `Magician.set_cp_params` {#set_cp_params}

```python
Magician.set_cp_params(plan_acc, junction_vel, acc=0.0, *, real_time_track=False) -> int
```

Set continuous-path planning parameters.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `plan_acc` | `float` | Planning acceleration, mm/s². Higher values give sharper corners. |
| `junction_vel` | `float` | Maximum velocity through a corner, mm/s. |
| `acc` | `float`, default `0.0` | Execution acceleration limit, mm/s². `0.0` uses the firmware default. |
| `real_time_track` | `bool`, default `False` | Enable real-time tracking mode. |

**Returns** `int`: queue index of the command.

**See also** [`cp`](motion.md#cp).

**Example**

```python
bot.set_cp_params(plan_acc=200, junction_vel=200, acc=200)
```
