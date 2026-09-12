# DobotLab Magician compatibility

`Magician` supports all **28 Python API entries** in the
[official DobotLab Dobot Magician manual](https://cdn.release.dobot.cc/dobotlab-doc/dobotlab/coding-manual-en/20260205/Dobot%20Magician/Dobot%20Magician.html)
(sections 3.6.1 through 3.6.28, February 2026 edition). The documented method
names and argument order are preserved, including the `motion_params` and
`jump_params` properties and the official `set_converyor` spelling.

## Official functions

Call these methods on a connected `Magician` instance:

| Manual section | Function or property |
| --- | --- |
| 3.6.1 | `ptp(mode, x, y, z, r)` |
| 3.6.2 | `set_device_withl(enable, version)` |
| 3.6.3 | `set_ptpl_params(vel, accel)` |
| 3.6.4 | `set_ptpwithl_cmd(mode, x, y, z, r, l)` |
| 3.6.5 | `set_r(r)` |
| 3.6.6 | `motion_params = vel, acc` |
| 3.6.7 | `jump_params = zlimit, height` |
| 3.6.8 | `set_multiplexing(io, multiplex)` |
| 3.6.9 | `set_pwm(io, freq, cycle)` |
| 3.6.10 | `set_do(io, level)` |
| 3.6.11 | `get_di(io)` |
| 3.6.12 | `get_adc(io)` |
| 3.6.13 | `set_endeffector_suctioncup(enable, on)` |
| 3.6.14 | `set_endeffector_gripper(enable, on)` |
| 3.6.15 | `set_infrared_sensor(port, enable, version)` |
| 3.6.16 | `get_infrared_sensor(port)` |
| 3.6.17 | `set_color_sensor(port, enable, version)` |
| 3.6.18 | `get_color_sensor()` |
| 3.6.19 | `wait(second)` |
| 3.6.20 | `set_home()` |
| 3.6.21 | `get_pose()` |
| 3.6.22 | `get_posel()` |
| 3.6.23 | `clear_alarm()` |
| 3.6.24 | `get_arm_speed_ratio(mode)` |
| 3.6.25 | `set_lost_step_params(value)` |
| 3.6.26 | `set_lost_step_cmd()` |
| 3.6.27 | `get_lost_step_result()` |
| 3.6.28 | `set_converyor(index, enable, speed)` |

`Dobot` is an alias for `Magician`. `Stepper1` and `Stepper2` select conveyor
motors 0 and 1. `set_conveyor` is also available as an alias for `set_converyor`.

## Return values and command completion

DobotLab describes completion booleans for many setters. pydobotlab exposes
firmware queue indices for queued commands, so a returned index means the
command was accepted. Use `wait_for(index)` or `wait_idle()` to wait for execution.
Immediate setters such as `clear_alarm`, `set_device_withl`, and
`set_lost_step_params` return `None` and raise an exception on communication failure.

`get_pose()` returns a `Pose` with named attributes and the same five-item
unpacking shape as DobotLab: `x, y, z, r, joints`. Sensor reads return the
values documented in the manual.

```python
from pydobotlab import Magician

with Magician() as robot:
    robot.motion_params = 50, 50
    command_index = robot.ptp(mode=1, x=220, y=0, z=50, r=0)
    robot.wait_for(command_index)
    print(robot.get_pose())
```

## Extended control

- [`ptp`](motion.md) accepts all ten DobotLab modes as integers or `PTPMode` values.
- [`move_to`](motion.md#move-to) adds waiting, timeouts, and motion-alarm handling
  to PTP moves. `set_home` also offers these optional controls.
- [`batch`, `wait_for`, and `wait_idle`](queue.md) coordinate queued commands.
- [Live pose streaming](pose-stream.md) reports position changes to callbacks.
- The [control panel and broker](../panel/broker.md) let scripts and the panel
  operate in parallel, including with multiple arms.

## Protocol references

The serial implementation follows the
[Dobot Communication Protocol V1.1.5](https://download.dobot.cc/product-manual/dobot-magician/pdf/en/Dobot-Communication-Protocol-V1.1.5.pdf)
and [Dobot's DobotLink implementation](https://github.com/Dobot-Arm/DobotLink/blob/main/Plugins/MagicDevicePlugin/Protocol2/DMagicianProtocol.cpp).
The [method-to-command table](../protocol/method-to-cmd.md) maps API calls to
packet IDs and layouts.
