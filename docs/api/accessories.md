# Accessories

Control the conveyor and slideway, and run lost-step detection.

The setters wait until the arm has executed the command (inside [`batch`](queue.md#batch), they only queue it), return `True`, and raise a [`DobotAlarmError`](errors.md#dobotalarmerror) subclass if the arm reports an alarm.

| Member | Description |
|---|---|
| [`Magician.set_converyor`](#set_converyor) | Run or stop a conveyor motor. |
| [`Magician.set_conveyor`](#set_conveyor) | Alias of `set_converyor`. |
| [`Magician.set_device_withl`](#set_device_withl) | Enable or disable the slideway. |
| [`Magician.set_ptpl_params`](#set_ptpl_params) | Set slideway velocity and acceleration ratios. |
| [`Magician.set_ptpwithl_cmd`](#set_ptpwithl_cmd) | Run a point-to-point move with a slideway move. |
| [`Magician.get_posel`](#get_posel) | Read the slideway position. |
| [`Magician.set_lost_step_params`](#set_lost_step_params) | Set the lost-step threshold. |
| [`Magician.set_lost_step_cmd`](#set_lost_step_cmd) | Run a lost-step check. |
| [`Magician.get_lost_step_result`](#get_lost_step_result) | Read the active alarm names. |

---

## Conveyor

### `Magician.set_converyor` {#set_converyor}

```python
Magician.set_converyor(index, enable, speed) -> bool
```

Run or stop a conveyor motor.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `index` | `int` | Motor: [`Magician.Stepper1`](magician.md#stepper1) (`0`) or `Magician.Stepper2` (`1`). |
| `enable` | `bool` | Power the motor. |
| `speed` | `float` | Speed, pulses per second. Negative values reverse the direction. Rounded to an integer. |

**Returns** `bool`: `True`.

**Example**

```python
bot.set_converyor(bot.Stepper1, True, 5000)
bot.set_converyor(bot.Stepper1, False, 0)
```

### `Magician.set_conveyor` {#set_conveyor}

```python
Magician.set_conveyor(index, enable, speed) -> bool
```

Alias of [`set_converyor`](#set_converyor).

---

## Slideway

### `Magician.set_device_withl` {#set_device_withl}

```python
Magician.set_device_withl(enable, version=0) -> bool
```

Enable or disable the slideway.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `enable` | `bool` | Enable the slideway. |
| `version` | `int`, default `0` | Slideway version. `0` for version 1, `1` for version 2. |

**Returns** `bool`: `True`.

### `Magician.set_ptpl_params` {#set_ptpl_params}

```python
Magician.set_ptpl_params(vel, accel) -> bool
```

Set the velocity and acceleration ratios of the slideway.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `vel` | `float` | Velocity ratio, percent, from 1 to 100. |
| `accel` | `float` | Acceleration ratio, percent, from 1 to 100. |

**Returns** `bool`: `True`.

### `Magician.set_ptpwithl_cmd` {#set_ptpwithl_cmd}

```python
Magician.set_ptpwithl_cmd(mode, x, y, z, r, l) -> bool
```

Run a point-to-point move that also moves the slideway.

Requires the slideway to be enabled with [`set_device_withl`](#set_device_withl).

**Parameters**

| Name | Type | Description |
|---|---|---|
| `mode` | [`PTPMode`](motion.md#ptpmode) or `int` | Trajectory mode. |
| `x`, `y`, `z`, `r` | `float` | Arm target, as in [`ptp`](motion.md#ptp). |
| `l` | `float` | Slideway position, mm. |

**Returns** `bool`: `True`.

### `Magician.get_posel` {#get_posel}

```python
Magician.get_posel() -> float
```

Read the slideway position.

**Returns** `float`: position, mm.

---

## Lost-step detection

### `Magician.set_lost_step_params` {#set_lost_step_params}

```python
Magician.set_lost_step_params(value) -> bool
```

Set the lost-step detection threshold.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `value` | `float` | Threshold, degrees. |

**Returns** `bool`: `True`.

### `Magician.set_lost_step_cmd` {#set_lost_step_cmd}

```python
Magician.set_lost_step_cmd() -> bool
```

Run a lost-step check.

**Returns** `bool`: `True`.

**Raises** [`DobotLostStepError`](errors.md#dobotloststeperror): a lost step was detected (alarms `LOST_STEP_J1` to `LOST_STEP_J4`).

### `Magician.get_lost_step_result` {#get_lost_step_result}

```python
Magician.get_lost_step_result() -> list[str]
```

Read the names of the active alarms.

**Returns** `list[str]`: active alarm names. A lost step appears as `LOST_STEP_J1` to `LOST_STEP_J4`.

**Example**

```python
try:
    bot.set_lost_step_cmd()
except DobotLostStepError:
    print(bot.get_lost_step_result())
```
