"""pydobotlab - pure-Python control library for the Dobot Magician robot arm.

Public surface kept small and stable; everything else lives in submodules.
"""

from __future__ import annotations

from .alarms import Alarm, AlarmSet
from .commands import CommandID
from .device import Dobot, Magician, Pose
from .discovery import (
    KNOWN_DOBOT_USB_IDS,
    DiscoveredDobot,
    Discovery,
    PortInfo,
    ProbeFailure,
    discover,
    discover_with_diagnostics,
    find_free_port,
    is_dobot,
    is_port_in_use,
    list_ports,
)
from .errors import (
    DobotAlarmError,
    DobotConnectionError,
    DobotError,
    DobotKinematicError,
    DobotPortInUseError,
    DobotProtocolError,
    DobotTimeoutError,
)
from .protocol import EndEffectorType, IOFunction, JOGCmd, JogMode, PTPMode

__all__ = [
    # Core
    "Magician",
    "Dobot",  # backwards-compat alias for Magician
    "Pose",
    "Alarm",
    "AlarmSet",
    "CommandID",
    "PTPMode",
    "JOGCmd",
    "JogMode",
    "EndEffectorType",
    "IOFunction",
    # Discovery (functions and class - both equivalent)
    "Discovery",
    "PortInfo",
    "DiscoveredDobot",
    "ProbeFailure",
    "KNOWN_DOBOT_USB_IDS",
    "list_ports",
    "discover",
    "discover_with_diagnostics",
    "find_free_port",
    "is_dobot",
    "is_port_in_use",
    # Errors
    "DobotError",
    "DobotProtocolError",
    "DobotTimeoutError",
    "DobotConnectionError",
    "DobotPortInUseError",
    "DobotAlarmError",
    "DobotKinematicError",
]

__version__ = "0.1.0.1"
