# Speed & motion parameters

The arm has independent velocity / acceleration ratios for **PTP** (trajectory moves) and **JOG** (live nudges), plus JUMP-mode parameters for pick-and-place trajectories. All "ratios" are percentages of the firmware's internal baseline (`0..100`); the control panel's speed slider drives them.

---

## `motion_params` *(property)* - `tuple[float, float]`

**Purpose.** Read or write the global PTP velocity and acceleration ratios.

**Getter - Returns.** `(vel_ratio, acc_ratio)` as floats `0..100`.

**Setter - Inputs.** `(vel_ratio, acc_ratio)`. Each is clamped to `0..100` server-side.

**Protocol.** [`GET_SET_PTP_COMMON_PARAMS`](../protocol/command-ids.md) (83). Get is read + immediate. Set is write + queued; param: `float32 vel | float32 acc`.

**Example.**

```python
bot.motion_params = (50.0, 50.0)  # half-speed PTP
print(bot.motion_params)  # (50.0, 50.0)
```

---

## `jump_params` *(property)* - `tuple[float, float]`

**Purpose.** Read or write the JUMP-mode parameters (`zlimit`, `height`).

* `height` - how far above the *higher* of the two endpoints the arm lifts before flying across.
* `zlimit` - an absolute upper Z bound the trajectory may never exceed.

The setter takes them in that **API order** (`zlimit, height`); the wire frame swaps to the official `(height, zlimit)` layout internally.

**Getter - Returns.** `(zlimit, height)` floats (mm).

**Setter - Inputs.** `(zlimit, height)`.

**Protocol.** [`GET_SET_PTP_JUMP_PARAMS`](../protocol/command-ids.md) (82). Get is read + immediate. Set is write + queued; wire param: `float32 jumpHeight | float32 zLimit` (8 bytes).

**Example.**

```python
bot.jump_params = (150.0, 30.0)  # zlimit = 150 mm, lift height = 30 mm
```

---

## `set_jog_common_params(vel_ratio, acc_ratio) -> int`

**Purpose.** Global JOG velocity / acceleration percentage (`0..100`). The panel's speed slider sends this whenever it moves so jogs honour the same setting as PTP.

**Inputs.** Both `float`, clamped to `0..100`.

**Returns.** `int` queued-command index.

**Protocol.** [`GET_SET_JOG_COMMON_PARAMS`](../protocol/command-ids.md) (72), write + queued. Param: `float32 vel | float32 acc`.

---

## `get_jog_common_params() -> tuple[float, float]`

**Purpose.** Read back the current `(vel_ratio, acc_ratio)` for JOG.

**Returns.** `(float, float)`.

**Protocol.** [`GET_SET_JOG_COMMON_PARAMS`](../protocol/command-ids.md) (72), read + immediate. Response payload: 2 little-endian `float32`.

---

## `get_arm_speed_ratio(mode) -> float`

**Purpose.** Convenience accessor for whichever common-params velocity matters in `mode`.

**Inputs.** `mode: int` - `0` = JOG, `1` = PTP.

**Returns.** `float` velocity ratio `0..100`.

**Protocol.** Issues a single read of either [`GET_SET_JOG_COMMON_PARAMS`](../protocol/command-ids.md) (72) or [`GET_SET_PTP_COMMON_PARAMS`](../protocol/command-ids.md) (83) depending on `mode`.

---

## `set_cp_params(plan_acc, junction_vel, acc=0.0, *, real_time_track=False) -> int`

**Purpose.** Tune the Continuous Path planner. Used together with [`cp()`](motion.md#cpx-y-z-velocity1000-mode1-int) to draw smooth blended trajectories without per-segment deceleration.

**Inputs.**

| Arg | Type | Default | Meaning |
|-----|------|---------|---------|
| `plan_acc` | `float` | – | Planning acceleration (mm/s²) used by the trajectory planner when smoothing corners. Higher = sharper corners. |
| `junction_vel` | `float` | – | Maximum velocity (mm/s) preserved through a corner. Lower = slower, smoother corners. |
| `acc` | `float` | `0.0` | Execution acceleration limit (mm/s²). `0.0` = firmware default. |
| `real_time_track` | `bool` | `False` | Almost never used. When `True`, the firmware streams CP execution position back via the alarms register. |

**Returns.** `int` queued-command index.

**Protocol.** [`GET_SET_CP_PARAMS`](../protocol/command-ids.md) (90), write + queued. Param: `f32 planAcc | f32 junctionVel | f32 acc | u8 realTimeTrack` (13 bytes).

**Typical values.** `(plan_acc=200, junction_vel=200, acc=200)` gives clean corners at modest speeds. Lower both `plan_acc` and `junction_vel` if you want very smooth arcs at the cost of speed.

---

## `set_ptpl_params(vel, accel) -> int`

**Purpose.** Slideway max velocity and acceleration percentages (`1..100`).

**Inputs.** Both `float`.

**Returns.** `int` queued-command index.

**Protocol.** [`GET_SET_PTP_L_PARAMS`](../protocol/command-ids.md) (85), write + queued.

---

## A note on baselines

Each ratio is multiplied by an internal "100% velocity" baseline:

* **PTP**: 200 mm/s (firmware default).
* **JOG**: 200 mm/s for X/Y/Z, 90 °/s for R and joints.

So `motion_params = (50, 50)` at the firmware's defaults gives ~100 mm/s in PTP; `set_jog_common_params(25, 25)` gives ~50 mm/s in JOG. (The simulator uses the same baselines.)
