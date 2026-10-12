# Pose stream

Poll the arm pose on a background thread.

| Member | Description |
|---|---|
| [`Magician.start_pose_stream`](#start_pose_stream) | Start polling the pose. |
| [`Magician.stop_pose_stream`](#stop_pose_stream) | Stop polling the pose. |

Usage patterns are described in [Streaming the pose](../guide/pose-stream.md).

---

## `Magician.start_pose_stream` {#start_pose_stream}

```python
Magician.start_pose_stream(callback=None, *, hz=50.0, on_error=None) -> queue.Queue
```

Start polling the pose on a background thread.

Polling continues after errors. [`disconnect`](magician.md#disconnect) stops the stream.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `callback` | callable, `queue.Queue`, or `None`, default `None` | Destination of each [`Pose`](motion.md#pose). A callable is called with each pose. A queue receives each pose. `None` creates a new queue. |
| `hz` | `float`, default `50.0` | Polling rate, Hz. |
| `on_error` | callable or `None`, default `None` | Called with the exception when polling, or `callback`, starts failing. `None` prints a message when failures start and when polling recovers. |

**Returns** `queue.Queue`: the queue that receives poses. Empty when `callback` is a callable.

**Raises**

- `RuntimeError`: a stream is already running on this instance.

**Example**

```python
poses = bot.start_pose_stream(hz=20)
print(poses.get(timeout=1.0))
bot.stop_pose_stream()
```

---

## `Magician.stop_pose_stream` {#stop_pose_stream}

```python
Magician.stop_pose_stream() -> None
```

Stop polling the pose. Has no effect if no stream is running.
