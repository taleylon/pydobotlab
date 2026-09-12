# Digital I/O & sensors

The Magician exposes 20 GP-numbered I/O pins through a fixed set of accessors. Each pin can be re-purposed (multiplexed) as digital out, PWM, digital in, or analog in.

pydobotlab accepts both the official "DO_01" / "DI_05" string names *and* raw GP-port integers as the `io` argument; you'll see both in the wild.

---

## `set_multiplexing(io, multiplex) -> int`

**Purpose.** Configure pin `io` as DO / PWM / DI / ADC / DI-with-pullup / DI-with-pulldown.

**Inputs.**

| Arg | Type | Meaning |
|-----|------|---------|
| `io` | `str` (e.g. `"DO_01"`) or `int` (GP port) | Which pin. |
| `multiplex` | [`IOFunction`](#iofunction) (or int 0..6) | What role. |

**Returns.** `int` queued-command index.

**Protocol.** [`GET_SET_IO_MULTIPLEXING`](../protocol/command-ids.md) (130), write + queued. Param: `u8 port | u8 function`.

---

## `set_do(io, level) -> int`

**Purpose.** Drive digital output `io` low (`0`) or high (`1`).

**Returns.** `int` queued-command index.

**Protocol.** [`GET_SET_IO_DO`](../protocol/command-ids.md) (131), write + queued.

---

## `set_pwm(io, freq, cycle) -> int`

**Purpose.** PWM on `io`.

**Inputs.**

| Arg | Type | Meaning |
|-----|------|---------|
| `io` | str/int | Pin. |
| `freq` | `float` | Frequency in Hz (`10..1_000_000`). |
| `cycle` | `float` | Duty cycle `0..100` (%). |

**Returns.** `int` queued-command index.

**Protocol.** [`GET_SET_IO_PWM`](../protocol/command-ids.md) (132), write + queued. Param: `u8 port | float32 freq | float32 cycle`.

---

## `get_di(io) -> int`

**Purpose.** Read digital input `io`. Returns `0` (low) or `1` (high).

**Protocol.** [`GET_IO_DI`](../protocol/command-ids.md) (133), read + immediate.

---

## `get_adc(io) -> int`

**Purpose.** Read analog input `io`. Returns 0..4095 (12-bit).

**Protocol.** [`GET_IO_ADC`](../protocol/command-ids.md) (134), read + immediate.

---

## `set_color_sensor(port, enable, version=0) -> int`

**Purpose.** Configure the colour sensor on a specific port.

**Inputs.**

| Arg | Type | Meaning |
|-----|------|---------|
| `port` | `int` | GP1 through GP6 (1 through 6), according to the sensor version. |
| `enable` | `bool` | Mount and power the sensor. |
| `version` | `int` | `0` = v1, `1` = v2 module. |

**Returns.** `int` queued-command index.

**Protocol.** [`GET_SET_COLOR_SENSOR`](../protocol/command-ids.md) (137), write + queued.

---

## `get_color_sensor() -> tuple[int, int, int]`

**Purpose.** Read `(r, g, b)` from the most-recently-configured colour sensor (each channel `0..255`).

**Returns.** `tuple[int, int, int]`.

**Protocol.** [`GET_SET_COLOR_SENSOR`](../protocol/command-ids.md) (137), read + immediate.

---

## `set_infrared_sensor(port, enable, version=1) -> int`

**Purpose.** Configure an IR / photoelectric sensor on GP1, GP2, GP4, or GP5.

**Returns.** `int` queued-command index.

**Protocol.** [`GET_SET_INFRARED_SENSOR`](../protocol/command-ids.md) (138), write + queued.

---

## `get_infrared_sensor(port) -> int`

**Purpose.** Read the IR sensor on `port`. `0` = nothing detected, `1` = object detected.

**Protocol.** [`GET_SET_INFRARED_SENSOR`](../protocol/command-ids.md) (138), read + immediate.

---

## `IOFunction`

`from pydobotlab import IOFunction`. The multiplexer codes used by `set_multiplexing()`.

| Member  | Value | Meaning |
|---------|-------|---------|
| `DUMMY` | 0     | Disconnected (idle). |
| `DO`    | 1     | Digital output. |
| `PWM`   | 2     | Pulse-width modulation output. |
| `DI`    | 3     | Digital input (no pull). |
| `ADC`   | 4     | Analog input. |
| `DIPU`  | 5     | Digital input with pull-up. |
| `DIPD`  | 6     | Digital input with pull-down. |
