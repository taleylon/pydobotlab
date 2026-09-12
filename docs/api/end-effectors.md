# End-effectors

The Magician supports three swappable end-effectors: a suction cup, a 1-DOF gripper, and a laser. Each one has an `enable` flag (mounts it as the active effector and powers the air pump / valve / driver) and an `on/off` flag (actually engages it).

> **Heads-up.** The "enable" verb confuses people. Think of it as "this effector is the one currently mounted, and its electronics are powered". The `on` argument then opens/closes the valve or grips/releases the jaws.

---

## `set_endeffector_suctioncup(enable, on) -> int`

**Purpose.** Suction-cup state.

**Inputs.**

| Arg | Type | Meaning |
|-----|------|---------|
| `enable` | `bool` | `True` = power the air pump and treat the suction cup as the active effector. |
| `on` | `bool` | `True` = open the suction valve (pick up); `False` = release. |

**Returns.** `int` queued-command index.

**Protocol.** [`GET_SET_END_EFFECTOR_SUCTION_CUP`](../protocol/command-ids.md) (62), write + queued. Param: `u8 enableCtrl | u8 on` (2 bytes).

---

## `set_endeffector_gripper(enable, on) -> int`

**Purpose.** Gripper state.

**Inputs.**

| Arg | Type | Meaning |
|-----|------|---------|
| `enable` | `bool` | Mounts and powers the gripper. |
| `on` | `bool` | `True` = grip; `False` = release. |

**Returns.** `int` queued-command index.

**Protocol.** [`GET_SET_END_EFFECTOR_GRIPPER`](../protocol/command-ids.md) (63), write + queued. Param: `u8 enableCtrl | u8 grip` (2 bytes).

---

## Pick-and-place pattern

```python
with Magician() as bot:
    bot.set_home()
    # Hover above pickup spot
    bot.move_to(200, 80, 60, 0)
    # Drop down, suck, lift
    bot.move_to(200, 80, -30, 0)
    bot.set_endeffector_suctioncup(enable=True, on=True)
    bot.move_to(200, 80, 60, 0)
    # Fly across
    bot.move_to(200, -80, 60, 0)
    # Drop down, release, lift
    bot.move_to(200, -80, -30, 0)
    bot.set_endeffector_suctioncup(enable=True, on=False)
    bot.move_to(200, -80, 60, 0)
    bot.set_home()
```

A more compact variant uses [`PTPMode.JUMP_XYZ`](motion.md#ptp-modes) to fly with a built-in lift:

```python
from pydobotlab import PTPMode

bot.jump_params = (150.0, 30.0)  # zlimit=150, lift=30 mm
bot.move_to(200, 80, -30, 0, mode=PTPMode.JUMP_XYZ)  # one-shot pick approach
```

---

## Laser

The laser end-effector uses a different command (and CP-mode trajectories for engraving). Use `bot.set_endeffector_laser(enable=True, on=True)` to queue a laser command. The underlying command is [`CommandID.GET_SET_END_EFFECTOR_LASER`](../protocol/command-ids.md) (61) if you need it.

The `EndEffectorType` enum (`from pydobotlab import EndEffectorType`) is exposed for completeness:

| Member        | Value |
|---------------|-------|
| `LASER`       | 0     |
| `SUCTION_CUP` | 1     |
| `GRIPPER`     | 2     |
