# Queue control

The Magician's firmware has an internal **command queue**. Most "set" commands are tagged `isQueued=1` so they're appended to that queue and executed in FIFO order, while reads and a few control commands run **immediately** outside the queue.

pydobotlab exposes the queue both implicitly (every queued method returns its assigned index, and `move_to`/`set_home` block on it for you) and explicitly (the methods on this page).

---

## `wait_for(index, *, timeout=None, poll=0.02, raise_on_alarm=True) -> None`

**Purpose.** Block until the firmware queue has executed up through `index`.

**Inputs.**

| Arg | Type | Default | Meaning |
|-----|------|---------|---------|
| `index` | `int` | – | Queue index (returned by an earlier queued call). |
| `timeout` | `float \| None` | `None` | Seconds to wait. `None` = wait forever. |
| `poll` | `float` | `0.02` | How often to check (seconds). |
| `raise_on_alarm` | `bool` | `True` | While polling, also call [`get_alarms()`](alarms.md). If any motion alarm bit fires (codes `0x10..0x77`), raise [`DobotKinematicError`](errors.md#dobotkinematicerror-extends-dobotalarmerror) immediately so we don't sit forever for a command the firmware refused. |

**Returns.** `None` once the queue has reached `index`.

**Raises.**
* [`DobotTimeoutError`](errors.md#dobottimeouterror) - `timeout` elapsed before the index was reached.
* [`DobotKinematicError`](errors.md#dobotkinematicerror-extends-dobotalarmerror) - motion alarm fired while waiting.

**Protocol.** Polls [`GET_QUEUED_CMD_CURRENT_INDEX`](../protocol/command-ids.md) (246) and (when `raise_on_alarm`) [`GET_ALARMS_STATE`](../protocol/command-ids.md) (20) on every tick.

---

## `wait_idle(*, timeout=None, poll=0.02, raise_on_alarm=True) -> None`

**Purpose.** Block until the queue has executed every command issued from this `Magician` instance - i.e. until it has reached the last queue index pydobotlab returned.

**Inputs.** Same as `wait_for`, minus `index`.

**Returns.** `None`.

**Protocol.** Same as `wait_for`.

---

## `start_queue() -> None`

**Purpose.** Resume execution of queued commands. (`connect()` calls this automatically when `auto_start_queue=True`.)

**Protocol.** [`SET_QUEUED_CMD_START_EXEC`](../protocol/command-ids.md) (240), write + immediate.

---

## `stop_queue() -> None`

**Purpose.** Pause execution of queued commands without throwing them away. New commands continue to be appended; nothing runs until you call `start_queue()` again.

**Protocol.** [`SET_QUEUED_CMD_STOP_EXEC`](../protocol/command-ids.md) (241), write + immediate.

---

## `force_stop_queue() -> None`

**Purpose.** Halt the in-flight motion *now*. Any current move stops mid-trajectory.

**Protocol.** [`SET_QUEUED_CMD_FORCE_STOP_EXEC`](../protocol/command-ids.md) (242), write + immediate.

---

## `clear_queue() -> None`

**Purpose.** Discard all queued commands and reset the firmware's queue counter to zero. pydobotlab also resets its internal `_last_queued_index` so subsequent `wait_idle` calls don't try to wait on a stale index.

**Protocol.** [`SET_QUEUED_CMD_CLEAR`](../protocol/command-ids.md) (245), write + immediate.

---

## `queued_cmd_current_index() -> int`

**Purpose.** Read the firmware's current queue execution pointer.

**Returns.** `int` - last-executed queue index.

**Protocol.** [`GET_QUEUED_CMD_CURRENT_INDEX`](../protocol/command-ids.md) (246), read + immediate. Response: `u64`.

---

## `queued_cmd_left_space() -> int`

**Purpose.** Read how many slots are still free in the firmware's queue buffer (handy if you're enqueueing a long program and need to throttle).

**Returns.** `int`.

**Protocol.** [`GET_QUEUED_CMD_LEFT_SPACE`](../protocol/command-ids.md) (247), read + immediate.

---

## `wait(second) -> int`

**Purpose.** Insert a pause of `second` seconds *into the firmware queue*. Use this to delay between queued moves without round-tripping back to Python.

**Inputs.** `second: float`.

**Returns.** `int` queued-command index.

**Protocol.** [`SET_WAIT_CMD`](../protocol/command-ids.md) (110), write + queued. Param: `u32 ms`.

`wait_seconds()` is kept as a deprecated alias.

---

## `batch()` - context manager

**Purpose.** A "lazy run" idiom DobotLab itself doesn't expose: pause the firmware queue, accumulate moves inside the block, resume execution on exit. Lets you queue a whole drawing first, then have the firmware run it as one continuous program at full motion-planning speed.

**Inputs.** None.

**Returns.** A context manager.

**Protocol.** Sends [`SET_QUEUED_CMD_STOP_EXEC`](../protocol/command-ids.md) (241) on entry, your moves while inside, then [`SET_QUEUED_CMD_START_EXEC`](../protocol/command-ids.md) (240) on exit.

**Example.**

```python
with bot.batch():
    for x, y in points:
        bot.move_to(x, y, 0, 0, wait=False)
# Queue resumes here - arm runs the whole sequence as one continuous program.
bot.wait_idle()
```
