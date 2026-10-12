# Control byte

The control byte of a [frame](frame-format.md) selects the get or set form of a command and whether it goes through the firmware queue.

## Layout

```
+---+---+---+---+---+---+---+---+
| 7 | 6 | 5 | 4 | 3 | 2 | 1 | 0 |
+---+---+---+---+---+---+---+---+
                          │   │
                          │   └── rw       (0 = get, 1 = set)
                          └────── isQueued (0 = immediate, 1 = queued)
```

Bits 2 to 7 are reserved and set to 0.

## Values

| Ctrl | Meaning | Examples |
|---|---|---|
| `0x00` | Get, immediate | `GetPose`, `GetAlarmsState`, `GetIODI` |
| `0x01` | Set, immediate | `SetJOGCmd`, `ClearAllAlarmsState`, `SetQueuedCmdStartExec` |
| `0x02` | Get, queued | Not used by pydobotlab. |
| `0x03` | Set, queued | `SetPTPCmd`, `SetHOMECmd`, `SetWAITCmd`, `SetEndEffector*` |

## Get and set share an ID

The get and set forms of a command use the same ID, and `rw` selects the form. `GET_ALARMS_STATE` and `CLEAR_ALL_ALARMS_STATE` both have ID 20: `ctrl=0x00` reads the alarm bitmask and `ctrl=0x01` clears it. Identify commands in a trace by the pair `(ID, rw)`.

## Queued and immediate commands

- Motion, wait, and I/O set commands are queued. The firmware executes them in order and returns their queue index.
- Jog and queue-control commands are immediate, so they take effect regardless of the state of the queue: `jog`, `jog_stop`, `clear_alarm`, `start_queue`, `stop_queue`, `force_stop_queue`, and `clear_queue`.
- Get commands are immediate.

## Constants

`from pydobotlab.protocol import CTRL_RW, CTRL_QUEUED`

| Name | Value |
|---|---|
| `CTRL_RW` | `0b01` |
| `CTRL_QUEUED` | `0b10` |
