# Low-level commands

Send protocol commands that have no dedicated method. Command IDs and parameter layouts are listed in the [Command ID table](../protocol/command-ids.md).

| Member | Description |
|---|---|
| [`Magician.send_command`](#send_command) | Send a command and return the response. |
| [`Magician.write_command`](#write_command) | Send an immediate set command. |
| [`Magician.queue_command`](#queue_command) | Queue a set command. |
| [`Magician.execute_command`](#execute_command) | Queue a set command and wait until it executes. |
| [`Magician.read_command`](#read_command) | Send a get command. |
| [`Frame`](#frame) | Decoded protocol frame. |
| [`CommandID`](#commandid) | Protocol command IDs. |
| [Parameter packing](#parameter-packing) | Encode and decode parameter bytes. |

---

## `Magician.send_command` {#send_command}

```python
Magician.send_command(command_id, params=b"", *, write, queued=False) -> Frame
```

Send a command and return the response.

Queued commands sent with this method are not tracked by [`wait_idle`](queue.md#wait_idle). Use [`queue_command`](#queue_command) instead.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `command_id` | [`CommandID`](#commandid) or `int` | Command ID. |
| `params` | `bytes`, default `b""` | Parameter bytes. |
| `write` | `bool` | `True` for a set command, `False` for a get command. |
| `queued` | `bool`, default `False` | Add the command to the firmware queue. |

**Returns** [`Frame`](#frame): the response.

**Raises**

- [`DobotConnectionError`](errors.md#dobotconnectionerror): the instance is not connected.

---

## `Magician.write_command` {#write_command}

```python
Magician.write_command(command_id, params=b"") -> Frame
```

Send a set command that executes immediately.

**Returns** [`Frame`](#frame): the response.

---

## `Magician.queue_command` {#queue_command}

```python
Magician.queue_command(command_id, params=b"") -> int
```

Add a set command to the firmware queue.

The index is tracked by [`wait_idle`](queue.md#wait_idle).

**Returns** `int`: queue index of the command.

---

## `Magician.execute_command` {#execute_command}

```python
Magician.execute_command(command_id, params=b"") -> bool
```

Queue a set command and wait until the arm has executed it, as the DobotLab functions do.

Inside [`batch`](queue.md#batch), the command is only queued.

**Returns** `bool`: `True`.

**Raises** [`DobotAlarmError`](errors.md#dobotalarmerror) subclass: the arm reported an alarm.

---

## `Magician.read_command` {#read_command}

```python
Magician.read_command(command_id, params=b"") -> Frame
```

Send a get command.

**Returns** [`Frame`](#frame): the response.

**Example**

```python
frame = bot.read_command(CommandID.GET_DEVICE_VERSION)
major, minor, revision = frame.params[:3]
```

---

## `Frame` {#frame}

```python
class pydobotlab.protocol.Frame(cmd_id, ctrl, params)
```

Decoded protocol frame. Immutable.

| Attribute | Type | Description |
|---|---|---|
| `cmd_id` | `int` | Command ID. |
| `ctrl` | `int` | Control byte. |
| `params` | `bytes` | Parameter bytes. |
| `rw` | `bool` | `True` for a set command. |
| `is_queued` | `bool` | `True` if the queued bit is set. |

The frame layout is described in [Frame format](../protocol/frame-format.md).

---

## `CommandID` {#commandid}

```python
class pydobotlab.CommandID(IntEnum)
```

Protocol command IDs, for example `CommandID.GET_POSE` (10). The full list is in the [Command ID table](../protocol/command-ids.md).

---

## Parameter packing

Functions in `pydobotlab.protocol`. All use little-endian byte order.

| Function | Description |
|---|---|
| `pack_u8(*values)` | Pack unsigned 8-bit integers. |
| `pack_u16(*values)` | Pack unsigned 16-bit integers. |
| `pack_u32(*values)` | Pack unsigned 32-bit integers. |
| `pack_u64(value)` | Pack one unsigned 64-bit integer. |
| `pack_floats(*values)` | Pack 32-bit floats. |
| `unpack_floats(data)` | Unpack 32-bit floats into a tuple. |
| `unpack_u64(data)` | Unpack one unsigned 64-bit integer. |

**Example**

```python
from pydobotlab.protocol import pack_floats

bot.execute_command(CommandID.GET_SET_PTP_COMMON_PARAMS, pack_floats(50.0, 50.0))
```
