# End effectors

Control the suction cup, gripper, and laser.

Each method waits until the arm has executed the command (inside [`batch`](queue.md#batch), it only queues it), returns `True`, and raises a [`DobotAlarmError`](errors.md#dobotalarmerror) subclass if the arm reports an alarm.

| Member | Description |
|---|---|
| [`Magician.set_endeffector_suctioncup`](#set_endeffector_suctioncup) | Set the suction cup state. |
| [`Magician.set_endeffector_gripper`](#set_endeffector_gripper) | Set the gripper state. |
| [`Magician.set_endeffector_laser`](#set_endeffector_laser) | Set the laser state. |
| [`EndEffectorType`](#endeffectortype) | End-effector identifiers. |

---

## `Magician.set_endeffector_suctioncup` {#set_endeffector_suctioncup}

```python
Magician.set_endeffector_suctioncup(enable, on) -> bool
```

Set the suction cup state.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `enable` | `bool` | Power the suction cup pump. |
| `on` | `bool` | `True` applies suction. `False` releases. |

**Returns** `bool`: `True`.

**Example**

```python
bot.set_endeffector_suctioncup(True, True)  # pick
bot.set_endeffector_suctioncup(True, False)  # release
```

---

## `Magician.set_endeffector_gripper` {#set_endeffector_gripper}

```python
Magician.set_endeffector_gripper(enable, on) -> bool
```

Set the gripper state.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `enable` | `bool` | Power the gripper. |
| `on` | `bool` | `True` closes the gripper. `False` opens it. |

**Returns** `bool`: `True`.

---

## `Magician.set_endeffector_laser` {#set_endeffector_laser}

```python
Magician.set_endeffector_laser(enable, on) -> bool
```

Set the laser state.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `enable` | `bool` | Power the laser driver. |
| `on` | `bool` | `True` turns the laser on. `False` turns it off. |

**Returns** `bool`: `True`.

---

## `EndEffectorType` {#endeffectortype}

```python
class pydobotlab.EndEffectorType(IntEnum)
```

End-effector identifiers.

| Member | Value |
|---|---|
| `LASER` | 0 |
| `SUCTION_CUP` | 1 |
| `GRIPPER` | 2 |
