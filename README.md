# pydobotlab

Python control for the **Dobot Magician** robot arm, with an optional desktop
control panel and a simulator for working without hardware. Communicates
over serial using `pyserial`; no vendor DLL or DobotStudio installation is required.

**[Documentation & homepage](https://taleylon.github.io/pydobotlab/)** ·
[API reference](https://taleylon.github.io/pydobotlab/api/overview/) ·
[GitHub](https://github.com/taleylon/pydobotlab) ·
[Report an issue](https://github.com/taleylon/pydobotlab/issues)

## Installation

Requires **Python 3.10 or newer**. Install in a virtual environment:

```bash
python -m pip install pydobotlab
```

For the optional PySide6 desktop panel:

```bash
python -m pip install "pydobotlab[gui]"
pydobotlab-panel
```

The base library requires only `pyserial`; Qt is installed only with the
`gui` extra. See the [installation guide](https://taleylon.github.io/pydobotlab/getting-started/install/)
for virtual environments, Windows drivers, and Linux serial-port permissions.
The project has been used on Ubuntu and Windows; macOS hardware has not been verified.

## Quick start

With the arm connected and its workspace clear:

```python
from pydobotlab import Magician, PTPMode

with Magician() as robot:  # auto-discover; or specify "/dev/ttyUSB0" / "COM3"
    robot.clear_alarm()
    robot.set_home()
    robot.move_to(220, 0, 50, mode=PTPMode.MOVJ_XYZ)
    pose = robot.get_pose()
    print(pose)
```

`print(pose)` displays `x`, `y`, `z`, `r`, and all four joint angles:

```text
Pose(x=220.00, y=0.00, z=50.00, r=0.00, joints=[0.00, 30.00, 45.00, 0.00])
```

The values above illustrate the format; actual joint angles depend on the robot's
pose. Access individual values with `pose.x`, `pose.y`, `pose.z`, `pose.r`, or
`pose.joints`. Positions are in millimetres and angles are in degrees. Display
values are rounded to two decimal places; the attributes keep their full precision.

`Dobot` is also available as an alias for `Magician`. The documented DobotLab
method names and parameters are preserved for existing scripts and teaching material.

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
        robot.move_to(220, 0, 50)
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

## Development

From a local checkout, including before the first PyPI release:

```bash
python -m pip install -e ".[dev,gui,docs]"
python -m pytest --timeout=30
ruff check .
ruff format --check .
mkdocs serve
```

See [contributor guidance](https://github.com/taleylon/pydobotlab/blob/main/CONTRIBUTING.md)
and the [publishing guide](https://taleylon.github.io/pydobotlab/publishing/).

## License

MIT. Maintained by Tal Eylon, <taleylon1@gmail.com>.
