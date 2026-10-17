"""Exception hierarchy for pydobotlab."""

from __future__ import annotations


class DobotError(Exception):
    """Base class for all pydobotlab errors."""


class DobotConfigError(DobotError):
    """The configuration file is unreadable or contains an invalid setting."""


class DobotConnectionError(DobotError):
    """Could not open / read / write the serial port."""


class DobotPortInUseError(DobotConnectionError):
    """The requested serial port is busy.

    Raised eagerly when a port is opened a second time *within this process*
    (caught via the in-process registry) and also when the OS refuses the
    second open (e.g. POSIX exclusive flock conflict, Windows "access denied"
    on a COM port another program holds). Never raised for a permission
    problem - that is :class:`DobotPermissionError`.
    """


class DobotPermissionError(DobotConnectionError):
    """The OS denied this user access to the serial port (Linux/macOS).

    Only raised after confirming the device node really is inaccessible to
    the current user. The message says what to fix, e.g. adding the user to
    the ``dialout`` group.
    """


class DobotProtocolError(DobotError):
    """A malformed or unexpected packet was received from the arm."""


class DobotTimeoutError(DobotError):
    """A command did not receive a response within the configured timeout."""


class DobotAlarmError(DobotError):
    """The arm reported one or more alarms.

    Subclasses name the alarm group. ``alarms`` lists the alarm names.
    """

    def __init__(self, alarms: list[str] | None = None, message: str = ""):
        self.alarms = alarms or []
        super().__init__(message or f"Dobot alarms active: {self.alarms}")


class DobotKinematicError(DobotAlarmError):
    """The arm could not plan or execute a move.

    Raised for planning and motion alarms (``PLAN_*``, ``MOVE_*``: unreachable
    target, joint limit, singularity) and for limit alarms (``LIMIT_*``). Clear
    planning and motion alarms with :meth:`Dobot.clear_alarm` or the panel's
    Clear Alarm button; a limit alarm ends when the joint is jogged back.
    """


class DobotOverspeedError(DobotAlarmError):
    """A joint exceeded its maximum speed (``OVERSPEED_J*`` alarms)."""


class DobotLostStepError(DobotAlarmError):
    """A joint lost steps (``LOST_STEP_J*`` alarms); home the arm again."""


class DobotSystemAlarmError(DobotAlarmError):
    """The arm reported a system fault (``PUBLIC_*`` alarms)."""
