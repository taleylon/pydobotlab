# Streaming the pose

The arm reports its pose only when asked. [`start_pose_stream`](../api/pose-stream.md#start_pose_stream) polls it on a background thread and delivers each [`Pose`](../api/motion.md#pose) to a queue or a callback. Examples assume a connected `Magician` named `bot`.

## Reading from a queue

```python
poses = bot.start_pose_stream(hz=30)
bot.ptp(mode=1, x=200, y=0, z=50, r=0)  # MOVJ_XYZ; poses arrive during the move
bot.stop_pose_stream()

while not poses.empty():
    pose = poses.get()
    print(f"x={pose.x:.1f}  y={pose.y:.1f}  z={pose.z:.1f}")
```

## Using a callback

```python
def log_pose(pose):
    print(f"{pose.x:.1f}, {pose.y:.1f}, {pose.z:.1f}")


bot.start_pose_stream(callback=log_pose, hz=10)
```

The callback runs on the stream thread.

## Handling failures

Polling continues when a read or the callback fails. Pass `on_error` to handle the first failure of each failing period. Without it, a message is printed when failures start and when polling recovers.

```python
bot.start_pose_stream(callback=log_pose, on_error=lambda error: print("pose stream:", error))
```

## Concurrency

- Pose reads execute immediately and run alongside queued motion.
- Commands from all threads that share a `Magician` are sent one at a time.
- A script and the control panel can stream from the same arm when both connect through the [broker](../api/broker.md), which is the default.
