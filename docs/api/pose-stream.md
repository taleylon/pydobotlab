# Real-time pose stream

The arm doesn't push pose updates on its own — there's no spontaneous "I moved" message in the protocol. To animate a UI or log motion, pydobotlab polls [`GET_POSE`](../protocol/command-ids.md) (10) on a background thread at a configurable rate and pushes results into a `Queue` (or calls a user callback).

This is what the control panel uses to drive its live X/Y/Z/R readout while a script is running.

---

## `start_pose_stream(callback=None, *, hz=50.0) -> Queue`

**Purpose.** Start polling pose at `hz` Hz on a background thread.

**Inputs.**

| Arg | Type | Default | Meaning |
|-----|------|---------|---------|
| `callback` | `Callable[[Pose], None]`, `Queue`, or `None` | `None` | Where to push samples. `None` = create a fresh `Queue` (most common). A `Queue` = push directly. A callable = invoke with each `Pose`. |
| `hz` | `float` | `50.0` | Polling rate. The arm caps out around 60 Hz over USB. |

**Returns.** `Queue[Pose]` — the sink the stream is pushing into. If `callback` was a callable, the returned queue is a fresh empty one (the callable still gets every sample).

**Raises.** `RuntimeError` if a stream is already running on this `Magician`.

**Protocol.** Each tick sends `GET_POSE` (10), read + immediate. No queued commands; the stream coexists with running motion.

**Example — read poses from a queue:**

```python
import queue

poses = bot.start_pose_stream(hz=30)
bot.move_to(200, 0, 50, 0, wait=False)

while bot.queued_cmd_current_index() < 1:
    try:
        p = poses.get(timeout=0.1)
        print(f"x={p.x:.1f}  y={p.y:.1f}  z={p.z:.1f}")
    except queue.Empty:
        pass

bot.stop_pose_stream()
```

**Example — pass a callback:**

```python
def log(p):
    print(f"{p.x:.1f}, {p.y:.1f}, {p.z:.1f}")


bot.start_pose_stream(callback=log, hz=10)
```

---

## `stop_pose_stream() -> None`

**Purpose.** Stop the streaming thread. Safe to call even if no stream is running. Called automatically by `disconnect()`.

**Returns.** `None`.

---

## Concurrency notes

* The pose stream is independent of the firmware queue — `GET_POSE` is immediate, so it interleaves with running PTP commands without disturbing them.
* The `SerialTransport` serialises every request/response pair, so the stream's reads can't overlap a script's writes mid-frame.
* If you want to stream pose *and* the panel is also running, route through the broker (the default): the broker fans out one transport across N clients without anyone getting partial frames.
