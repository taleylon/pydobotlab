# Control byte (`rw` / `isQueued`)

The frame's **control byte** is one of the most consequential parts of the protocol - it picks which "side" of a command ID you're invoking and whether your command goes through the firmware's queue.

## Layout

```
+---+---+---+---+---+---+---+---+
| 7 | 6 | 5 | 4 | 3 | 2 | 1 | 0 |
+---+---+---+---+---+---+---+---+
                          │   │
                          │   └── rw       (0 = read / get,
                          │                 1 = write / set)
                          └────── isQueued (0 = run now / immediate,
                                            1 = append to queue)
```

Bits 2..7 are reserved (always 0).

## The four meaningful values

| Ctrl   | Hex   | Meaning                       | Example commands                        |
|--------|-------|-------------------------------|-----------------------------------------|
| `0b00` | `0x00`| read, immediate               | `GetPose`, `GetAlarmsState`, `GetDi`    |
| `0b01` | `0x01`| write, immediate              | `SetJOGCmd`, `ClearAllAlarmsState`, `SetQueuedCmdStartExec` |
| `0b10` | `0x02`| read, queued (rare/unused)    | n/a in normal use                       |
| `0b11` | `0x03`| write, queued                 | `SetPTPCmd`, `SetHOMECmd`, `SetEndEffector*`, `SetWAITCmd` |

## Why same ID, different meanings

Most commands have a *get* and a *set* form, and the protocol uses **the same command ID** for both - the `rw` bit picks which one. For example `CommandID.GET_ALARMS_STATE = 20` and `CommandID.CLEAR_ALL_ALARMS_STATE = 20` share the same numeric ID; sending `ctrl=0x00` reads the alarm bitmask, sending `ctrl=0x01` clears it.

This bites you if you build your own protocol-spying tool: filter on `(cmd_id, rw_bit)`, not on `cmd_id` alone.

## Why JOG goes immediate, PTP goes queued

There's a load-bearing rule of thumb here.

* **PTP / HOME / wait / queued I/O are queued.** They're parts of a *program* the arm executes in order, with one trajectory completing before the next begins. The queue is *the* execution model for trajectory motion.
* **JOG is immediate.** A jog is a live nudge; you press a button, the firmware starts integrating velocity, you release, the firmware stops. If JOG went through the queue, two things would break:
  1. A jog would stack up behind your last PTP and only run once that finished - useless for "live" motion.
  2. **When an alarm fires, the queue is paused.** A queued JOG-IDLE on button release wouldn't execute until you cleared the alarm, so the arm would keep moving with no way to stop it. (This was real bug #3 in pydobotlab's hardware-test pass - fixed by sending JOG immediate.)

So in pydobotlab:

```python
def jog(self, cmd, mode=JogMode.COORDINATE) -> Frame:
    return self.write_command(  # ← immediate, not queue_command!
        CommandID.SET_JOG_CMD, pack_u8(int(mode), int(cmd))
    )
```

Same logic for `clear_alarm`, `clear_queue`, `start_queue`, `stop_queue`, `force_stop_queue` - they're all queue-control commands and must reach the firmware *now*, regardless of queue state.

## Constants

`from pydobotlab.protocol import CTRL_RW, CTRL_QUEUED`

| Name          | Value  |
|---------------|--------|
| `CTRL_RW`     | `0b01` |
| `CTRL_QUEUED` | `0b10` |
