# I/O and sensors

Configure and use the I/O pins, the color sensor, and infrared sensors.

The setters wait until the arm has executed the command (inside [`batch`](queue.md#batch), they only queue it), return `True`, and raise a [`DobotAlarmError`](errors.md#dobotalarmerror) subclass if the arm reports an alarm.

| Member | Description |
|---|---|
| [`Magician.set_multiplexing`](#set_multiplexing) | Set the function of an I/O pin. |
| [`Magician.set_do`](#set_do) | Set a digital output. |
| [`Magician.set_pwm`](#set_pwm) | Set a PWM output. |
| [`Magician.get_di`](#get_di) | Read a digital input. |
| [`Magician.get_adc`](#get_adc) | Read an analog input. |
| [`Magician.set_color_sensor`](#set_color_sensor) | Enable or disable the color sensor. |
| [`Magician.get_color_sensor`](#get_color_sensor) | Read the color sensor. |
| [`Magician.set_infrared_sensor`](#set_infrared_sensor) | Enable or disable an infrared sensor. |
| [`Magician.get_infrared_sensor`](#get_infrared_sensor) | Read an infrared sensor. |
| [`IOFunction`](#iofunction) | I/O pin functions. |

## Pin references

The `io` parameter accepts a label or a number from 1 to 20. Labels have the prefix `DO`, `DI`, `AD`, or `AI`, an optional underscore, and the pin number, for example `"DO_01"`, `"DI_5"`, or `"AD3"`. The prefix does not change the pin addressed. Other values raise `ValueError`.

---

## `Magician.set_multiplexing` {#set_multiplexing}

```python
Magician.set_multiplexing(io, multiplex) -> bool
```

Set the function of an I/O pin.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `io` | `str` or `int` | Pin. See [Pin references](#pin-references). |
| `multiplex` | [`IOFunction`](#iofunction) or `int` | Pin function. |

**Returns** `bool`: `True`.

**Example**

```python
bot.set_multiplexing("DO_01", IOFunction.DO)
bot.set_do("DO_01", 1)
```

---

## `Magician.set_do` {#set_do}

```python
Magician.set_do(io, level) -> bool
```

Set a digital output.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `io` | `str` or `int` | Pin. See [Pin references](#pin-references). |
| `level` | `int` | `0` for low. Any other value sets high. |

**Returns** `bool`: `True`.

---

## `Magician.set_pwm` {#set_pwm}

```python
Magician.set_pwm(io, freq, cycle) -> bool
```

Set a PWM output.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `io` | `str` or `int` | Pin. See [Pin references](#pin-references). |
| `freq` | `float` | Frequency, Hz, from 10 to 1,000,000. |
| `cycle` | `float` | Duty cycle, percent. |

**Returns** `bool`: `True`.

---

## `Magician.get_di` {#get_di}

```python
Magician.get_di(io) -> int
```

Read a digital input.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `io` | `str` or `int` | Pin. See [Pin references](#pin-references). |

**Returns** `int`: `0` for low, `1` for high.

---

## `Magician.get_adc` {#get_adc}

```python
Magician.get_adc(io) -> int
```

Read an analog input.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `io` | `str` or `int` | Pin. See [Pin references](#pin-references). |

**Returns** `int`: value from 0 to 4095.

---

## `Magician.set_color_sensor` {#set_color_sensor}

```python
Magician.set_color_sensor(port, enable, version=0) -> bool
```

Enable or disable the color sensor.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `port` | `int` | Port, `1` to `6` for GP1 to GP6. |
| `enable` | `bool` | Enable the sensor. |
| `version` | `int`, default `0` | Sensor version. `0` for version 1, `1` for version 2. |

**Returns** `bool`: `True`.

---

## `Magician.get_color_sensor` {#get_color_sensor}

```python
Magician.get_color_sensor() -> tuple[int, int, int]
```

Read the color sensor.

**Returns** `tuple[int, int, int]`: `(r, g, b)`, each from 0 to 255.

**Example**

```python
bot.set_color_sensor(2, True)
r, g, b = bot.get_color_sensor()
```

---

## `Magician.set_infrared_sensor` {#set_infrared_sensor}

```python
Magician.set_infrared_sensor(port, enable, version=1) -> bool
```

Enable or disable an infrared sensor.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `port` | `int` | Port: `1`, `2`, `4`, or `5` for GP1, GP2, GP4, or GP5. |
| `enable` | `bool` | Enable the sensor. |
| `version` | `int`, default `1` | Sensor version. `0` for version 1, `1` for version 2. |

**Returns** `bool`: `True`.

---

## `Magician.get_infrared_sensor` {#get_infrared_sensor}

```python
Magician.get_infrared_sensor(port) -> int
```

Read an infrared sensor.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `port` | `int` | Port of the sensor. |

**Returns** `int`: `1` if an object is detected, otherwise `0`.

---

## `IOFunction` {#iofunction}

```python
class pydobotlab.IOFunction(IntEnum)
```

I/O pin functions for [`set_multiplexing`](#set_multiplexing).

| Member | Value | Description |
|---|---|---|
| `DUMMY` | 0 | Unused. |
| `DO` | 1 | Digital output. |
| `PWM` | 2 | PWM output. |
| `DI` | 3 | Digital input. |
| `ADC` | 4 | Analog input. |
| `DIPU` | 5 | Digital input with pull-up. |
| `DIPD` | 6 | Digital input with pull-down. |
