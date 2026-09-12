# API Reference - Overview

Start with the [28 official DobotLab Magician functions](dobotlab.md), then use
the extended motion, queue, and streaming APIs as needed. All robot commands go
through one class:

```python
from pydobotlab import Magician
```

`Magician` is the high-level Dobot Magician driver. (It's also exported as `Dobot` for backward compatibility with very old code; new code should prefer `Magician`.)

## The shape of every page

Every page in this section follows the same layout so you can scan it quickly:

* **Group purpose** - one paragraph saying what the methods on this page are for.
* **Methods** - for each public method:
  * Python signature
  * **Purpose** - what it does in plain English.
  * **Inputs** - argument-by-argument table.
  * **Returns** - what comes back.
  * **Raises** - exceptions you might see.
  * **Protocol** - the underlying [Dobot CommandID](../protocol/command-ids.md) and notes on how pydobotlab uses it (queued vs. immediate, packed parameter layout).
  * **Notes** / **Example** - gotchas and a code snippet.

Because most Magician methods send exactly one Dobot frame, the **Protocol** entry is the bridge between the friendly Python API and the wire-level [Dobot Communication Protocol V1.1.5](https://download.dobot.cc/product-manual/dobot-magician/pdf/en/Dobot-Communication-Protocol-V1.1.5.pdf). If you ever need to debug what's actually going down the serial line, that's where you look.

## Methods by category

| Category | Page |
|----------|------|
| Connection lifecycle (`connect`, `disconnect`, `is_open`, ...) | [Connection lifecycle](connection.md) |
| Cartesian / joint motion (`move_to`, `ptp`, `set_home`, `set_r`) | [Pose & motion](motion.md) |
| Live JOG nudges (`jog`, `jog_stop`) | [JOG](jog.md) |
| Velocity & acceleration ratios, JUMP params (`motion_params`, `jump_params`, ...) | [Speed & motion parameters](speed.md) |
| Reading and clearing alarms (`get_alarms`, `clear_alarm`, `ensure_no_alarms`) | [Alarms](alarms.md) |
| Firmware queue (`start_queue`, `wait_for`, `wait_idle`, `batch`) | [Queue control](queue.md) |
| Suction cup, gripper (`set_endeffector_*`) | [End-effectors](end-effectors.md) |
| Digital I/O and sensors (`set_do`, `get_di`, `set_color_sensor`, ...) | [Digital I/O & sensors](io.md) |
| Conveyor, slideway, lost-step (`set_conveyor`, `set_ptpwithl_cmd`, ...) | [Conveyor & extras](extras.md) |
| Real-time pose stream (`start_pose_stream`, `stop_pose_stream`) | [Real-time pose stream](pose-stream.md) |
| Finding arms (`Discovery`, `find_free_port`, `is_dobot`) | [Discovery](discovery.md) |
| Exception hierarchy | [Errors & exceptions](errors.md) |

## Constants & enums you'll see

| Symbol | Where | What |
|--------|-------|------|
| [`PTPMode`](motion.md#ptp-modes) | `pydobotlab.protocol` | Mode selector for `ptp()` (JUMP / MOVJ / MOVL × XYZ / ANGLE / INC). |
| [`JOGCmd`](jog.md#jogcmd) | `pydobotlab.protocol` | Direction selector for `jog()` (`AP_DOWN`, `AN_DOWN`, …). |
| [`JogMode`](jog.md#jogmode) | `pydobotlab.protocol` | Coordinate vs. joint frame for `jog()`. |
| [`EndEffectorType`](end-effectors.md) | `pydobotlab.protocol` | Identifier for the active end-effector. |
| [`IOFunction`](io.md#iofunction) | `pydobotlab.protocol` | DO/PWM/DI/ADC/PullUp/PullDn for `set_multiplexing()`. |
| [`Alarm`](alarms.md#alarm-codes) | `pydobotlab.alarms` | Named bit positions in the firmware's 128-bit alarm mask. |
| [`CommandID`](../protocol/command-ids.md) | `pydobotlab.commands` | The underlying Dobot protocol command IDs. |

## A word on returned values

Methods that **set** state and go through the firmware's queue (`ptp`, `set_home`, `set_endeffector_*`, ...) return the **queue index** assigned to that command - a monotonically increasing integer the firmware uses to tell you when it has executed your command. You can hand it to [`wait_for()`](queue.md#wait_forindex-timeoutnone-poll002-raise_on_alarmtrue-none) to block until it runs, or ignore it for fire-and-forget execution.

Methods that **read** state (`get_pose`, `get_alarms`, `get_di`, ...) return the value directly.

Methods that go **immediate** (no queue: `clear_alarm`, `clear_queue`, `start_queue`, `jog`, `jog_stop`, ...) return either `None`, the parsed `Frame`, or the value of interest - see each page for specifics.
