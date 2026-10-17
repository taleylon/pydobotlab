"""Constants of the control panel, kept in ``panel.toml`` next to this module."""

from __future__ import annotations

import tomllib
from pathlib import Path

PANEL_CONFIG_PATH = Path(__file__).with_name("panel.toml")

with PANEL_CONFIG_PATH.open("rb") as file:
    PANEL_CONFIG: dict = tomllib.load(file)
