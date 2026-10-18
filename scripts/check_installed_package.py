"""Smoke-check an installed wheel. Run with python -I to exclude the checkout."""

from importlib.metadata import distribution, version
from importlib.resources import files

import pydobotlab
from pydobotlab import Dobot
from pydobotlab.config import default_config
from pydobotlab.panel.alarm_text import short_text
from pydobotlab.panel.app import parse_arguments
from pydobotlab.panel.panel_config import PANEL_CONFIG
from pydobotlab.simulator import install_simulator, stop_all

assert pydobotlab.__version__ == version("pydobotlab")
assert files("pydobotlab.panel").joinpath("style.qss").read_text(encoding="utf-8").strip()
assert files("pydobotlab").joinpath("config.toml").read_text(encoding="utf-8").strip()
assert files("pydobotlab.panel").joinpath("panel.toml").read_text(encoding="utf-8").strip()
assert files("pydobotlab.panel").joinpath("icon.png").read_bytes().startswith(b"\x89PNG")
assert files("pydobotlab.panel").joinpath("icon.ico").read_bytes()[:4] == b"\x00\x00\x01\x00"
assert parse_arguments(["--create-shortcut"]).create_shortcut
assert short_text(0x44) == "The forearm (J3) reached its limit. Jog J3- to move it back."
assert "require_panel=False" in default_config()["messages"]["panel_not_running"]
assert PANEL_CONFIG["hub"]["quit_dialog"]["title"]
assert parse_arguments(["--simulator"]).simulator
assert parse_arguments(["--dev"]).dev
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
