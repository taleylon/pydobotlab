# Conveyor & extras

The miscellaneous corners: the optional conveyor / slideway accessories, lost-step detection, and device-info getters.

---

## Conveyor

### `set_conveyor(index, enable, speed) -> int`

**Purpose.** Drive a stepper-conveyor.

**Inputs.**

| Arg | Type | Meaning |
|-----|------|---------|
| `index` | `int` | `0` = Stepper1, `1` = Stepper2. |
| `enable` | `bool` | Power the stepper driver. |
| `speed` | `float` | Pulses/second. Negative reverses direction. |

**Returns.** `int` queued-command index.

**Protocol.** [`SET_E_MOTOR`](../protocol/command-ids.md) (135), write + queued. Param: `u8 index | u8 enable | int32 speed`.

> **Naming.** The official Dobot SDK has a typo in this function's name (`set_converyor`). pydobotlab keeps the typo verbatim *and* exposes `set_conveyor` as a properly-spelled alias.

---

## Slideway (linear rail)

### `set_device_withl(enable, version=0) -> int`

**Purpose.** Enable/disable the slideway and declare its hardware version (`0` = V1, `1` = V2).

**Returns.** `int` queued-command index.

**Protocol.** [`GET_SET_DEVICE_WITH_L`](../protocol/command-ids.md) (3), write + queued.

### `set_ptpl_params(vel, accel) -> int`

See [Speed & motion parameters](speed.md#set_ptpl_paramsvel-accel-int).

### `set_ptpwithl_cmd(mode, x, y, z, r, l) -> int`

See [Pose & motion](motion.md#set_ptpwithl_cmdmode-x-y-z-r-l-int).

### `get_posel() -> float`

See [Pose & motion](motion.md#get_posel-float).

---

## Lost-step detection

A lost step happens when a joint's commanded position drifts from its measured position past a configurable threshold - usually because a motion was forced too hard.

### `set_lost_step_params(value) -> int`

**Purpose.** Set the lost-step detection threshold (degrees).

**Returns.** `int` queued-command index.

**Protocol.** [`GET_SET_LOST_STEP_PARAMS`](../protocol/command-ids.md) (170), write + queued.

### `set_lost_step_cmd() -> int`

**Purpose.** Trigger a single lost-step detection pass. If a joint exceeds the threshold, a `LOST_STEP_J*` alarm bit is set.

**Returns.** `int` queued-command index.

**Protocol.** [`SET_LOST_STEP_CMD`](../protocol/command-ids.md) (171), write + queued.

### `get_lost_step_result() -> list[str]`

**Purpose.** Convenience wrapper - returns the names of currently-active alarms (any of which might be `LOST_STEP_J*`).

**Protocol.** Re-reads [`GET_ALARMS_STATE`](../protocol/command-ids.md) (20).

---

## Device info

These are read-side commands that don't move the arm.

### `get_device_serial_number() -> str`

**Protocol.** [`GET_DEVICE_SN`](../protocol/command-ids.md) (0), read + immediate.

### `get_device_name() -> str`

**Protocol.** [`GET_SET_DEVICE_NAME`](../protocol/command-ids.md) (1), read + immediate.

### `set_device_name(name) -> None`

**Protocol.** [`GET_SET_DEVICE_NAME`](../protocol/command-ids.md) (1), write + queued.

### `get_device_version() -> tuple[int, int, int]`

**Purpose.** Firmware version `(major, minor, revision)`. Pure transport probe - used by the connection watchdog.

**Protocol.** [`GET_DEVICE_VERSION`](../protocol/command-ids.md) (2), read + immediate.
