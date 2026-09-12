# JOG (live, non-trajectory motion)

JOG is the firmware's mode for **live nudges** — push a button, the arm starts moving along that axis; release the button, it stops. Unlike PTP, there is no trajectory; the arm just integrates a velocity until the next JOG command tells it otherwise.

The control panel's directional buttons (X+/X−/Y+/Y−/Z+/Z−/R+/R− and J1+/J1−/...) are JOG.

> **Important — immediate frames.**
> pydobotlab sends JOG as **immediate** (`isQueued=0`) frames, not queued ones. This is on purpose: when the firmware is in an alarm state the queue is paused, so a queued JOG-IDLE on button release would sit unexecuted and the arm would keep moving. Sending immediate makes start *and* stop reach the firmware regardless of queue state. See the [Control byte](../protocol/ctrl-byte.md) page.

---

## `jog(cmd, mode=JogMode.COORDINATE) -> Frame`

**Purpose.** Start (or stop) a JOG.

**Inputs.**

| Arg | Type | Default | Meaning |
|-----|------|---------|---------|
| `cmd` | [`JOGCmd`](#jogcmd) (or int) | – | Direction. `IDLE` (0) stops; `AP_DOWN`..`DN_DOWN` (1..8) start an axis. |
| `mode` | [`JogMode`](#jogmode) | `COORDINATE` | Whether `cmd` is in Cartesian (X/Y/Z/R) or joint (J1..J4) space. |

**Returns.** [`Frame`](../protocol/frame-format.md#frame-format) — the firmware's parsed acknowledgement.

**Protocol.** [`SET_JOG_CMD`](../protocol/command-ids.md) (73), write + **immediate**. Param: `u8 isJoint | u8 cmd` (2 bytes). Response payload: empty (just an ack).

**Example.**

```python
from pydobotlab import Magician, JOGCmd, JogMode
import time

with Magician() as bot:
    bot.jog(JOGCmd.AP_DOWN, JogMode.COORDINATE)  # start X+
    time.sleep(0.5)
    bot.jog_stop()  # stop
```

---

## `jog_stop() -> None`

**Purpose.** Stop any active JOG. Best-effort: retries once on a transport error because a stuck jog is a safety hazard.

**Inputs.** None.

**Returns.** `None`.

**Raises.** Doesn't propagate transport errors — eats them after one retry.

**Protocol.** Sends `SET_JOG_CMD` with `cmd=JOGCmd.IDLE`.

---

## `JOGCmd`

`from pydobotlab import JOGCmd`. Used as the `cmd` argument to `jog()`.

| Member       | Value | In `COORDINATE` mode | In `JOINT` mode |
|--------------|-------|----------------------|-----------------|
| `IDLE`       | 0     | stop                 | stop            |
| `AP_DOWN`    | 1     | X+                   | J1+             |
| `AN_DOWN`    | 2     | X−                   | J1−             |
| `BP_DOWN`    | 3     | Y+                   | J2+             |
| `BN_DOWN`    | 4     | Y−                   | J2−             |
| `CP_DOWN`    | 5     | Z+                   | J3+             |
| `CN_DOWN`    | 6     | Z−                   | J3−             |
| `DP_DOWN`    | 7     | R+                   | J4+             |
| `DN_DOWN`    | 8     | R−                   | J4−             |

(The naming `*_DOWN` matches the official Dobot SDK and dates from "key down" terminology in DobotLab — it does *not* mean the Z axis.)

---

## `JogMode`

`from pydobotlab import JogMode`. Picks the frame `cmd` is interpreted in.

| Member       | Value | Meaning |
|--------------|-------|---------|
| `COORDINATE` | 0     | Cartesian: X / Y / Z / R. |
| `JOINT`      | 1     | Joints: J1 / J2 / J3 / J4. |

---

## How fast does JOG move?

JOG speed is set globally for all jogs by [`set_jog_common_params(vel_ratio, acc_ratio)`](speed.md#set_jog_common_paramsvel_ratio-acc_ratio-int) — both numbers are percentages (`0..100`) of the firmware's full-speed baseline. The control panel's speed slider drives this.

To read back the current ratios: [`get_jog_common_params()`](speed.md#get_jog_common_params-tuplefloat-float) returns `(vel_ratio, acc_ratio)`.
