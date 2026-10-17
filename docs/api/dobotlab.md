# DobotLab compatibility

`Magician` implements the 28 Python functions in the [DobotLab Dobot Magician manual](https://cdn.release.dobot.cc/dobotlab-doc/dobotlab/coding-manual-en/20260205/Dobot%20Magician/Dobot%20Magician.html) (sections 3.6.1 to 3.6.28, February 2026 edition) with the same names and argument order.

| Section | Function |
|---|---|
| 3.6.1 | [`ptp(mode, x, y, z, r)`](motion.md#ptp) |
| 3.6.2 | [`set_device_withl(enable, version)`](accessories.md#set_device_withl) |
| 3.6.3 | [`set_ptpl_params(vel, accel)`](accessories.md#set_ptpl_params) |
| 3.6.4 | [`set_ptpwithl_cmd(mode, x, y, z, r, l)`](accessories.md#set_ptpwithl_cmd) |
| 3.6.5 | [`set_r(r)`](motion.md#set_r) |
| 3.6.6 | [`motion_params = vel, acc`](speed.md#motion_params) |
| 3.6.7 | [`jump_params = zlimit, height`](speed.md#jump_params) |
| 3.6.8 | [`set_multiplexing(io, multiplex)`](io.md#set_multiplexing) |
| 3.6.9 | [`set_pwm(io, freq, cycle)`](io.md#set_pwm) |
| 3.6.10 | [`set_do(io, level)`](io.md#set_do) |
| 3.6.11 | [`get_di(io)`](io.md#get_di) |
| 3.6.12 | [`get_adc(io)`](io.md#get_adc) |
| 3.6.13 | [`set_endeffector_suctioncup(enable, on)`](end-effectors.md#set_endeffector_suctioncup) |
| 3.6.14 | [`set_endeffector_gripper(enable, on)`](end-effectors.md#set_endeffector_gripper) |
| 3.6.15 | [`set_infrared_sensor(port, enable, version)`](io.md#set_infrared_sensor) |
| 3.6.16 | [`get_infrared_sensor(port)`](io.md#get_infrared_sensor) |
| 3.6.17 | [`set_color_sensor(port, enable, version)`](io.md#set_color_sensor) |
| 3.6.18 | [`get_color_sensor()`](io.md#get_color_sensor) |
| 3.6.19 | [`wait(second)`](queue.md#wait) |
| 3.6.20 | [`set_home()`](motion.md#set_home) |
| 3.6.21 | [`get_pose()`](motion.md#get_pose) |
| 3.6.22 | [`get_posel()`](accessories.md#get_posel) |
| 3.6.23 | [`clear_alarm()`](alarms.md#clear_alarm) |
| 3.6.24 | [`get_arm_speed_ratio(mode)`](speed.md#get_arm_speed_ratio) |
| 3.6.25 | [`set_lost_step_params(value)`](accessories.md#set_lost_step_params) |
| 3.6.26 | [`set_lost_step_cmd()`](accessories.md#set_lost_step_cmd) |
| 3.6.27 | [`get_lost_step_result()`](accessories.md#get_lost_step_result) |
| 3.6.28 | [`set_converyor(index, enable, speed)`](accessories.md#set_converyor) |

## Differences

- When the arm reports an alarm, a function raises a [`DobotAlarmError`](errors.md#dobotalarmerror) subclass instead of returning `False`.
- [`clear_alarm`](alarms.md#clear_alarm) also raises when an alarm is active again after clearing.
- [`set_home`](motion.md#set_home) homes also during an alarm, as the Home button of DobotLab does, and clears the alarms when homing ends.
- Inside [`batch`](queue.md#batch), the functions queue their command and return at once.
- `get_pose()` returns a [`Pose`](motion.md#pose), which unpacks as `x, y, z, r, joints`.
- [`set_conveyor`](accessories.md#set_conveyor) is an alias for `set_converyor`. [`Magician.Stepper1` and `Magician.Stepper2`](magician.md#stepper1) select conveyor motors 0 and 1.

## Example

```python
from pydobotlab import Magician

with Magician() as robot:
    robot.motion_params = 50, 50
    robot.ptp(mode=1, x=220, y=0, z=50, r=0)  # MOVJ_XYZ
    print(robot.get_pose())
```
