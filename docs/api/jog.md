# Jogging

Move continuously along one Cartesian axis or one joint until stopped.

| Member | Description |
|---|---|
| [`Magician.jog`](#jog) | Start or stop jog motion. |
| [`Magician.jog_stop`](#jog_stop) | Stop jog motion. |
| [`JOGCmd`](#jogcmd) | Jog directions. |
| [`JogMode`](#jogmode) | Cartesian or joint jogging. |

Jog velocity and acceleration are set with [`set_jog_common_params`](speed.md#set_jog_common_params).

---

## `Magician.jog` {#jog}

```python
Magician.jog(cmd, mode=JogMode.COORDINATE) -> Frame
```

Start or stop jog motion.

Motion continues until the next `jog` call or [`jog_stop`](#jog_stop). Jog commands execute immediately and bypass the command queue.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `cmd` | [`JOGCmd`](#jogcmd) or `int` | Direction. `JOGCmd.IDLE` stops. |
| `mode` | [`JogMode`](#jogmode), default `JogMode.COORDINATE` | Interpret `cmd` as a Cartesian axis or a joint. |

**Returns** [`Frame`](low-level.md#frame): acknowledgement from the arm.

**Example**

```python
bot.jog(JOGCmd.AP_DOWN)  # start moving in +X
time.sleep(0.5)
bot.jog_stop()
```

---

## `Magician.jog_stop` {#jog_stop}

```python
Magician.jog_stop() -> None
```

Stop jog motion.

Retries once if sending the stop command fails.

**Raises**

- [`DobotConnectionError`](errors.md#dobotconnectionerror) or [`DobotTimeoutError`](errors.md#dobottimeouterror): the retry also failed. The arm may still be moving.

---

## `JOGCmd` {#jogcmd}

```python
class pydobotlab.JOGCmd(IntEnum)
```

Jog directions for [`jog`](#jog).

| Member | Value | `COORDINATE` mode | `JOINT` mode |
|---|---|---|---|
| `IDLE` | 0 | Stop | Stop |
| `AP_DOWN` | 1 | X+ | J1+ |
| `AN_DOWN` | 2 | X- | J1- |
| `BP_DOWN` | 3 | Y+ | J2+ |
| `BN_DOWN` | 4 | Y- | J2- |
| `CP_DOWN` | 5 | Z+ | J3+ |
| `CN_DOWN` | 6 | Z- | J3- |
| `DP_DOWN` | 7 | R+ | J4+ |
| `DN_DOWN` | 8 | R- | J4- |

---

## `JogMode` {#jogmode}

```python
class pydobotlab.JogMode(IntEnum)
```

Frame in which [`jog`](#jog) interprets its direction.

| Member | Value | Description |
|---|---|---|
| `COORDINATE` | 0 | Cartesian axes X, Y, Z, and R. |
| `JOINT` | 1 | Joints J1 to J4. |
