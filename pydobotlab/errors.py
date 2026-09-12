"""Exception hierarchy for pydobotlab."""

from __future__ import annotations


class DobotError(Exception):
    """Base class for all pydobotlab errors."""


class DobotConnectionError(DobotError):
    """Could not open / read / write the serial port."""


class DobotPortInUseError(DobotConnectionError):
    """The requested serial port is already claimed by another Dobot instance.

    Raised eagerly when a port is opened a second time *within this process*
    (caught via the in-process registry) and also when the OS refuses the
    second open (e.g. POSIX exclusive flock conflict).
    """


class DobotProtocolError(DobotError):
    """A malformed or unexpected packet was received from the arm."""


class DobotTimeoutError(DobotError):
    """A command did not receive a response within the configured timeout."""


class DobotAlarmError(DobotError):
    """The arm reported one or more alarms while a command was pending."""

    def __init__(self, alarms: list[str] | None = None, message: str = ""):
        self.alarms = alarms or []
        super().__init__(message or f"Dobot alarms active: {self.alarms}")


class DobotKinematicError(DobotAlarmError):
    """A motion command failed because the firmware couldn't plan or execute it.

    Raised by :meth:`Dobot.move_to`, :meth:`Dobot.set_home`,
    :meth:`Dobot.wait_for`, :meth:`Dobot.wait_idle` (and any other waiter)
    when one of the well-known motion-failure alarms fires:

    * ``PLAN_INVERSE_RESOLVE`` — IK solver couldn't find a solution.
    * ``PLAN_MOTION_TARGET_OUT_OF_WORKSPACE`` — target outside reach.
    * ``KINEMATIC_TARGET_OUT_OF_WORKSPACE`` — same, kinematic side.
    * ``PLAN_INVERSE_LIMIT`` / ``KINEMATIC_INVERSE_LIMIT`` — IK hit a joint limit.
    * ``PLAN_IN_SINGULARITY_ZONE`` / ``KINEMATIC_SINGULARITY`` — singular.
    * ``PLAN_CURRENT_JOINT_OUT_OF_RANGE`` — start pose already off-range.
    * ``LIMIT_POS_J*`` / ``LIMIT_NEG_J*`` — joint limit struck mid-motion.

    To recover, the student must call :meth:`Dobot.clear_alarm` (the panel's
    "Clear Alarm" button does the same thing). Any motion command that
    follows will retry from a clean state.
    """
