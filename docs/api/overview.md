# API reference

This reference describes every public object in pydobotlab. Objects are importable from the top-level `pydobotlab` package unless the page names a submodule.

## Sections

| Section | Contents |
|---|---|
| [DobotLab compatibility](dobotlab.md) | The 28 DobotLab Magician functions and where each is documented. |
| [Magician](magician.md) | Constructor, connection, and device information. |
| [Motion](motion.md) | Pose reading, point-to-point and continuous-path moves, homing. |
| [Jogging](jog.md) | Continuous motion along one axis or joint. |
| [Motion parameters](speed.md) | Velocity, acceleration, JUMP, and continuous-path parameters. |
| [Command queue](queue.md) | Waiting on, pausing, and clearing the firmware command queue. |
| [Alarms](alarms.md) | Reading and clearing alarms. |
| [End effectors](end-effectors.md) | Suction cup, gripper, and laser. |
| [I/O and sensors](io.md) | Digital and analog I/O, PWM, color and infrared sensors. |
| [Accessories](accessories.md) | Conveyor, slideway, and lost-step detection. |
| [Pose stream](pose-stream.md) | Background pose polling. |
| [Low-level commands](low-level.md) | Raw protocol commands and parameter packing. |
| [Discovery](discovery.md) | Finding and probing serial ports. |
| [Broker](broker.md) | Sharing one arm between several clients. |
| [Simulator](simulator.md) | Simulated arms for use without hardware. |
| [Configuration](config.md) | Per-user file with the default settings. |
| [Exceptions](errors.md) | Exception hierarchy. |

## Conventions

- Lengths are in millimetres, angles in degrees, durations in seconds, and ratios in percent (0 to 100).
- The DobotLab functions that change the arm state wait until the arm has executed the command and return `True`. They raise a [`DobotAlarmError`](errors.md#dobotalarmerror) subclass when the arm reports an alarm.
- Other methods that queue a command, such as [`cp`](motion.md#cp), return its firmware queue index (`int`). Pass the index to [`wait_for`](queue.md#wait_for) to block until the command executes.
- Read methods return the value read. Other immediate commands return `None` unless stated otherwise.
- Examples assume that the names they use are imported from `pydobotlab` and that `bot` is a connected instance:

    ```python
    from pydobotlab import Magician

    bot = Magician()
    bot.connect()
    ```

- The protocol command sent by each method is listed in [Method ↔ command mapping](../protocol/method-to-cmd.md).

## Deprecated aliases

| Alias | Use instead |
|---|---|
| `Magician.home` | [`Magician.set_home`](motion.md#set_home) |
| `Magician.clear_alarms` | [`Magician.clear_alarm`](alarms.md#clear_alarm) |
| `Magician.wait_seconds` | [`Magician.wait`](queue.md#wait) |
| `Magician.get_pose_l` | [`Magician.get_posel`](accessories.md#get_posel) |
| `Magician.get_slideway_pose` | [`Magician.get_posel`](accessories.md#get_posel) |
| `AlarmSet.describe` | [`AlarmSet.format`](alarms.md#alarmset) |

## Version

`pydobotlab.__version__` is the installed package version as a string.
