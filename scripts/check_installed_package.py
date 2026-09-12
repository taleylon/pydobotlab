"""Smoke-check an installed wheel. Run with python -I to exclude the checkout."""

from importlib.metadata import distribution, version
from importlib.resources import files

import pydobotlab
from pydobotlab import Dobot
from pydobotlab.panel.app import parse_arguments
from pydobotlab.simulator import install_simulator, stop_all

assert pydobotlab.__version__ == version("pydobotlab")
assert files("pydobotlab.panel").joinpath("style.qss").read_text(encoding="utf-8").strip()
assert parse_arguments(["--simulator"]).simulator
entry_points = distribution("pydobotlab").entry_points
assert any(entry.name == "pydobotlab-panel" and callable(entry.load()) for entry in entry_points)
install_simulator(arms=1)
try:
    with Dobot("/dev/sim0", via_broker=False) as robot:
        assert robot.get_device_serial_number() == "SIM-MAGICIAN"
        assert robot.jump_params == (100.0, 20.0)
        robot.move_to(210, 0, 50, timeout=5)
        assert abs(robot.get_pose().x - 210) < 0.1
finally:
    stop_all()
print(f"Installed pydobotlab {pydobotlab.__version__} OK: {pydobotlab.__file__}")
