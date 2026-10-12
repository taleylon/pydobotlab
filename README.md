# pydobotlab

This project was created out of necessity as an alternative to the heavy DobotLab software officially provided by Dobot. It is designed specifically for the **Dobot Magician** and provides full coverage of the 28 Python API entries documented in the [official DobotLab Magician manual](https://cdn.release.dobot.cc/dobotlab-doc/dobotlab/coding-manual-en/20260205/Dobot%20Magician/Dobot%20Magician.html).
It uses the documented function names and arguments for motion, I/O, sensors, end effectors, the slideway, and the conveyor. It runs on Windows and Linux (tested on Ubuntu 24 and 26), and may also run on macOS, although macOS has not yet been tested.

The official DobotLab software, which is implemented with compiled DLLs, is heavy and creates an unfriendly barrier to accessing the robot for educational purposes. This project implements the available commands directly in pure Python using the original protocol ([Dobot Communication Protocol V1.1.5](https://taleylon.github.io/pydobotlab/Dobot-Communication-Protocol-V1.1.5.pdf)). Because the robot connects via USB, the project can run on any operating system that supports Python and can communicate with the robot.

This project uses `pyserial` to communicate with the robot, so no vendor DLL or DobotStudio installation is required. Arm specifications and workspace information are available in the [Dobot Magician V2 User Guide (DobotLab-based) V2.3.1](https://taleylon.github.io/pydobotlab/Dobot-Magician-V2-User-Guide-V2.3.1.pdf).

In addition, this project:
- Provides a Qt-based panel that mimics the DobotLab control panel and operates without interfering with other programs communicating with the robot.
- Supports communication with one robot **or more**, allowing several robots to be controlled from a single workstation.
- Implements a simulator that can be used to test the robot's behavior without having one connected.

**[Documentation & homepage](https://taleylon.github.io/pydobotlab/)** ·
[API reference](https://taleylon.github.io/pydobotlab/api/overview/) ·
[GitHub](https://github.com/taleylon/pydobotlab) ·
[Changelog](https://github.com/taleylon/pydobotlab/blob/main/CHANGELOG.md) ·
[Report an issue](https://github.com/taleylon/pydobotlab/issues)

## Installation

Requires **Python 3.11 or newer**. Install in a virtual environment:

```bash
python -m pip install pydobotlab
```

For the optional PySide6 desktop panel:

```bash
python -m pip install "pydobotlab[gui]"
pydobotlab-panel
```

The base library requires only `pyserial`; Qt is
installed only with the `gui` extra. Default settings are read from a per-user
[configuration file](https://taleylon.github.io/pydobotlab/api/config/). See the [installation guide](https://taleylon.github.io/pydobotlab/getting-started/install/)
for virtual environments, Windows drivers, and Linux serial-port permissions.
The project has been used on Ubuntu and Windows; macOS hardware has not been verified.

## Quick start

With the arm connected and its workspace clear:

```python
from pydobotlab import Magician

with Magician() as robot:  # auto-discover; or specify "/dev/ttyUSB0" / "COM3"
    robot.clear_alarm()
    robot.set_home()
    robot.ptp(mode=1, x=220, y=0, z=50, r=0)  # MOVJ_XYZ; returns when the arm arrives
    pose = robot.get_pose()
    print(pose)
```

`print(pose)` displays `x`, `y`, `z`, `r`, and all four joint angles:

```text
Pose(x=220.00, y=0.00, z=50.00, r=0.00, joints=[0.00, 30.00, 45.00, 0.00])
```

The values above illustrate the format; actual joint angles depend on the robot's
pose. Access individual values with `pose.x`, `pose.y`, `pose.z`, `pose.r`, or
`pose.joints`. Positions are in millimetres and angles are in degrees.

`Dobot` is also available as an alias for `Magician`. The documented DobotLab
method names and parameters are preserved for existing scripts.

As in DobotLab, `ptp` and the other commands return `True` once the arm has
executed them, so each command starts after the previous one has ended. When the
arm reports an alarm, such as an unreachable target, the command raises an
exception that names the alarm and its fix, and the program stops.

```python
with Magician() as robot:
    robot.ptp(mode=1, x=220, y=0, z=50, r=0)  # MOVJ_XYZ
    robot.ptp(mode=2, x=220, y=40, z=50, r=0)  # MOVL_XYZ
    robot.set_endeffector_suctioncup(enable=True, on=True)
```

See [DobotLab compatibility](https://taleylon.github.io/pydobotlab/api/dobotlab/)
for the complete function list and return-value conventions.

## Try it without hardware

```bash
pydobotlab-panel --simulator
```

Or use the simulator from Python:

```python
from pydobotlab import Magician
from pydobotlab.simulator import install_simulator, stop_all

install_simulator(arms=1)
try:
    with Magician("/dev/sim0", via_broker=False) as robot:
        robot.ptp(mode=1, x=220, y=0, z=50, r=0)  # MOVJ_XYZ
        print(robot.get_pose())
finally:
    stop_all()
```

The simulator supports offline examples and tests. It approximates motion
and firmware behavior; it does not validate a real robot's trajectory.

## Features and examples

- Cartesian and joint motion, jogging, homing, speed settings, and continuous paths.
- Suction cup, gripper, laser, digital I/O, sensors, and conveyor commands.
- Structured alarms, motion-failure exceptions, and live pose streaming.
- Firmware queue control and `with robot.batch()` for accumulating commands.
- Multiple robot connections and a local broker for sharing a port between the GUI and scripts.

Start with [pick and place](https://github.com/taleylon/pydobotlab/blob/main/examples/pick_and_place.py),
[smiley drawing](https://github.com/taleylon/pydobotlab/blob/main/examples/draw_smiley.py),
or [two arms with live panels](https://github.com/taleylon/pydobotlab/blob/main/examples/two_dobots_with_panels.py).
The [user guide](https://taleylon.github.io/pydobotlab/) covers the API,
control panel, broker, and wire protocol.

## License

MIT. 


_Maintained by Tal Eylon, <taleylon1@gmail.com>._
