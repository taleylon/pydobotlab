# Command queue

Commands that change the arm state are appended to the firmware command queue and run in order. The DobotLab functions, such as [`ptp`](motion.md#ptp), wait for their own command. These members wait on, pause, and clear the queue.

| Member | Description |
|---|---|
| [`Magician.wait_for`](#wait_for) | Block until a queued command has executed. |
| [`Magician.wait_idle`](#wait_idle) | Block until every command queued by this instance has executed. |
| [`Magician.wait`](#wait) | Pause the arm. |
| [`Magician.batch`](#batch) | Queue commands and run them when the block exits. |
| [`Magician.start_queue`](#start_queue) | Start executing queued commands. |
| [`Magician.stop_queue`](#stop_queue) | Pause execution of queued commands. |
| [`Magician.force_stop_queue`](#force_stop_queue) | Stop execution immediately. |
| [`Magician.clear_queue`](#clear_queue) | Remove all queued commands. |
| [`Magician.queued_cmd_current_index`](#queued_cmd_current_index) | Read the index of the last executed command. |
| [`Magician.queued_cmd_left_space`](#queued_cmd_left_space) | Read the free space in the queue. |

---

## `Magician.wait_for` {#wait_for}

```python
Magician.wait_for(index, *, timeout=None, poll=0.02, raise_on_alarm=True) -> None
```

Block until the queue has executed the command at `index`.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `index` | `int` | Queue index returned by a queued command. |
| `timeout` | `float` or `None`, default `None` | Maximum wait, seconds. `None` waits indefinitely. |
| `poll` | `float`, default `0.02` | Polling interval, seconds. |
| `raise_on_alarm` | `bool`, default `True` | Raise as soon as any alarm is active. Commands still queued are then discarded. |

**Raises**

- [`DobotAlarmError`](errors.md#dobotalarmerror) subclass: an alarm is active while waiting.
- [`DobotTimeoutError`](errors.md#dobottimeouterror): `timeout` elapsed.

**Example**

```python
index = bot.move_to(200, 0, 50, mode=1, wait=False)  # MOVJ_XYZ
bot.wait_for(index, timeout=10)
```

---

## `Magician.wait_idle` {#wait_idle}

```python
Magician.wait_idle(*, timeout=None, poll=0.02, raise_on_alarm=True) -> None
```

Block until the queue has executed every command queued by this instance.

Returns immediately if nothing has been queued since connecting or since the last [`clear_queue`](#clear_queue).

**Parameters**

| Name | Type | Description |
|---|---|---|
| `timeout` | `float` or `None`, default `None` | Maximum wait, seconds. `None` waits indefinitely. |
| `poll` | `float`, default `0.02` | Polling interval, seconds. |
| `raise_on_alarm` | `bool`, default `True` | Raise as soon as any alarm is active. Commands still queued are then discarded. |

**Raises**

- [`DobotAlarmError`](errors.md#dobotalarmerror) subclass: an alarm is active while waiting.
- [`DobotTimeoutError`](errors.md#dobottimeouterror): `timeout` elapsed.

---

## `Magician.wait` {#wait}

```python
Magician.wait(second) -> bool
```

Pause the arm for `second` seconds and wait until the pause ends.

Inside [`batch`](#batch), the pause is queued and the method returns at once.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `second` | `float` | Pause duration, seconds. Rounded to milliseconds. |

**Returns** `bool`: `True`.

---

## `Magician.batch` {#batch}

```python
Magician.batch()
```

Context manager that queues commands and runs them when the block exits.

On entry, stops and clears the queue. Inside the block, the DobotLab functions only queue their command. On exit, starts the queue and waits until every command has executed. If the block raises, the queued commands are discarded. Nested blocks take effect only at the outermost level. `move_to` with `wait=True`, `wait_for`, and `wait_idle` do not return inside the block.

**Returns** A context manager that yields the `Magician` instance.

**Raises** [`DobotAlarmError`](errors.md#dobotalarmerror) subclass: the arm reported an alarm while running the commands.

**Example**

```python
with bot.batch():
    for x, y in points:
        bot.ptp(mode=2, x=x, y=y, z=50, r=0)  # MOVL_XYZ
```

---

## `Magician.start_queue` {#start_queue}

```python
Magician.start_queue() -> None
```

Start executing queued commands.

[`connect`](magician.md#connect) calls this method when `auto_start_queue=True`.

---

## `Magician.stop_queue` {#stop_queue}

```python
Magician.stop_queue() -> None
```

Pause execution of queued commands.

Queued commands are kept, and new commands can still be queued.

---

## `Magician.force_stop_queue` {#force_stop_queue}

```python
Magician.force_stop_queue() -> None
```

Stop execution of queued commands immediately, including the command in progress.

---

## `Magician.clear_queue` {#clear_queue}

```python
Magician.clear_queue() -> None
```

Remove all queued commands.

---

## `Magician.queued_cmd_current_index` {#queued_cmd_current_index}

```python
Magician.queued_cmd_current_index() -> int
```

Read the index of the last executed queued command.

---

## `Magician.queued_cmd_left_space` {#queued_cmd_left_space}

```python
Magician.queued_cmd_left_space() -> int
```

Read the number of free slots in the firmware queue.
