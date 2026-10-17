"""Alarm decoding for the Dobot Magician.

The arm reports active alarms as a 16-byte (128-bit) bitmask returned by
``GetAlarmsState`` (cmd ID 20). Each bit corresponds to one named alarm; the
alarm "ID" is conventionally written in hex from ``0x00`` to ``0x7F`` and
maps to ``(byte_index, bit_within_byte) = (id // 8, id % 8)``.

The codes, their meaning, and how each alarm ends follow the Dobot Magician
ALARM Description V1.0.1 (``docs/Dobot-Magician-ALARM-Description.pdf``). A set
bit whose code is not in that document is still reported, labelled by its
code range (for example ``LIMIT_0x4A``), so it is not dropped.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import IntEnum

from .errors import (
    DobotAlarmError,
    DobotKinematicError,
    DobotLostStepError,
    DobotOverspeedError,
    DobotSystemAlarmError,
)


class Alarm(IntEnum):
    """Named alarm codes. Value = bit position within the 128-bit mask."""

    # ---- Public (system) faults: 0x00 to 0x0F -------------------------------
    PUBLIC_RESET = 0x00
    PUBLIC_UNDEFINED_INSTRUCTION = 0x01
    PUBLIC_FILE_SYSTEM = 0x02
    PUBLIC_MCU_COMM = 0x03  # between the MCU and the FPGA, at start-up
    PUBLIC_ANGLE_SENSOR_READ = 0x04

    # ---- Planning, when a command is planned: 0x10 to 0x1F ------------------
    PLAN_INVERSE_SINGULARITY = 0x10  # target in an abnormal position
    PLAN_INVERSE_CALCULATION = 0x11  # target out of the workspace
    PLAN_INVERSE_LIMIT = 0x12  # target needs a joint beyond its limit
    PLAN_DATA_REPEAT = 0x13  # repeated points in ARC or JUMP_MOVL
    PLAN_ARC_INPUT_PARAMETER = 0x14
    PLAN_JUMP_PARAMETER = 0x15

    # ---- Motion, while the arm moves: 0x20 to 0x2F --------------------------
    MOVE_INVERSE_SINGULARITY = 0x20
    MOVE_INVERSE_CALCULATION = 0x21  # path leaves the workspace
    MOVE_INVERSE_LIMIT = 0x22  # path needs a joint beyond its limit

    # ---- Overspeed per joint: 0x30 to 0x3F ----------------------------------
    OVERSPEED_J1 = 0x30
    OVERSPEED_J2 = 0x31
    OVERSPEED_J3 = 0x32
    OVERSPEED_J4 = 0x33

    # ---- Joint limits: 0x40 to 0x4F, positive and negative per joint ---------
    LIMIT_POS_J1 = 0x40
    LIMIT_NEG_J1 = 0x41
    LIMIT_POS_J2 = 0x42
    LIMIT_NEG_J2 = 0x43
    LIMIT_POS_J3 = 0x44
    LIMIT_NEG_J3 = 0x45
    LIMIT_POS_J4 = 0x46
    LIMIT_NEG_J4 = 0x47
    LIMIT_POS_PARALLELOGRAM = 0x48  # rear arm and forearm stretched apart
    LIMIT_NEG_PARALLELOGRAM = 0x49

    # ---- Lost step per joint: 0x50 to 0x5F ----------------------------------
    LOST_STEP_J1 = 0x50
    LOST_STEP_J2 = 0x51
    LOST_STEP_J3 = 0x52
    LOST_STEP_J4 = 0x53


# One "{tag}: {explanation + fix}" line per known alarm. Surfaced in both
# the panel banner and the DobotKinematicError message so a student can see
# what went wrong AND what to do about it without leaving the IDE.
_TROUBLESHOOT: dict[Alarm, str] = {
    # System
    Alarm.PUBLIC_RESET: "the arm was reset - call clear_alarm()",
    Alarm.PUBLIC_UNDEFINED_INSTRUCTION: "the arm received an unknown command - call clear_alarm()",
    Alarm.PUBLIC_FILE_SYSTEM: "file system error - power-cycle the arm",
    Alarm.PUBLIC_MCU_COMM: "MCU-FPGA communication failed at start-up - power-cycle the arm",
    Alarm.PUBLIC_ANGLE_SENSOR_READ: "an angle sensor gave a wrong value - power-cycle the arm",
    # Planning
    Alarm.PLAN_INVERSE_SINGULARITY: "target is in an abnormal position - pick another target, then clear_alarm()",
    Alarm.PLAN_INVERSE_CALCULATION: "target is outside the workspace - pick a reachable target, then clear_alarm()",
    Alarm.PLAN_INVERSE_LIMIT: "target needs a joint beyond its limit (J1 -90..90, J2 0..85, J3 -10..90, J4 -90..90) - pick another target, then clear_alarm()",
    Alarm.PLAN_DATA_REPEAT: "repeated points in an ARC or JUMP_MOVL move - change the points, then clear_alarm()",
    Alarm.PLAN_ARC_INPUT_PARAMETER: "invalid ARC points - change them, then clear_alarm()",
    Alarm.PLAN_JUMP_PARAMETER: "invalid JUMP parameters, such as a negative height - fix jump_params, then clear_alarm()",
    # Motion
    Alarm.MOVE_INVERSE_SINGULARITY: "the path passes a singular pose - change the path, then clear_alarm()",
    Alarm.MOVE_INVERSE_CALCULATION: "the path leaves the workspace - change the path, then clear_alarm()",
    Alarm.MOVE_INVERSE_LIMIT: "the path needs a joint beyond its limit - change the path, then clear_alarm()",
    # Overspeed
    Alarm.OVERSPEED_J1: "joint 1 over speed - lower motion_params (e.g. 30, 30), then clear_alarm()",
    Alarm.OVERSPEED_J2: "joint 2 over speed - lower motion_params (e.g. 30, 30), then clear_alarm()",
    Alarm.OVERSPEED_J3: "joint 3 over speed - lower motion_params (e.g. 30, 30), then clear_alarm()",
    Alarm.OVERSPEED_J4: "joint 4 over speed - lower motion_params (e.g. 30, 30), then clear_alarm()",
    # Joint limits: each ends by itself when the joint is jogged back off the limit.
    Alarm.LIMIT_POS_J1: "joint 1 (base) at its positive limit - jog J1 negative",
    Alarm.LIMIT_NEG_J1: "joint 1 (base) at its negative limit - jog J1 positive",
    Alarm.LIMIT_POS_J2: "joint 2 (rear arm) at its positive limit - jog J2 negative",
    Alarm.LIMIT_NEG_J2: "joint 2 (rear arm) at its negative limit - jog J2 positive",
    Alarm.LIMIT_POS_J3: "joint 3 (forearm) at its positive limit - jog J3 negative",
    Alarm.LIMIT_NEG_J3: "joint 3 (forearm) at its negative limit - jog J3 positive",
    Alarm.LIMIT_POS_J4: "joint 4 (end-effector rotation) at its positive limit - jog J4 negative",
    Alarm.LIMIT_NEG_J4: "joint 4 (end-effector rotation) at its negative limit - jog J4 positive",
    Alarm.LIMIT_POS_PARALLELOGRAM: "rear arm and forearm stretched to their limit - jog back the way the arm came",
    Alarm.LIMIT_NEG_PARALLELOGRAM: "rear arm and forearm folded to their limit - jog back the way the arm came",
    # Lost step
    Alarm.LOST_STEP_J1: "joint 1 lost steps - call set_home()",
    Alarm.LOST_STEP_J2: "joint 2 lost steps - call set_home()",
    Alarm.LOST_STEP_J3: "joint 3 lost steps - call set_home()",
    Alarm.LOST_STEP_J4: "joint 4 lost steps - call set_home()",
}

# Range of each alarm group (its first code), as a label and a fallback remedy
# for codes in the range that the document does not name.
GROUP_LABELS: dict[int, str] = {
    0x00: "SYSTEM",
    0x10: "PLAN",
    0x20: "MOVE",
    0x30: "OVERSPEED",
    0x40: "LIMIT",
    0x50: "LOST_STEP",
}
_BAND_TROUBLESHOOT: dict[int, str] = {
    0x00: "system fault - power-cycle the arm",
    0x10: "planning failed - pick another target, then clear_alarm()",
    0x20: "motion failed - change the path, then clear_alarm()",
    0x30: "a joint is too fast - lower motion_params, then clear_alarm()",
    0x40: "a joint is at a limit - jog it back",
    0x50: "a joint lost steps - call set_home()",
}


# Backwards-compat: AlarmSet.describe() used to read this dict directly.
_DESCRIPTIONS: dict[Alarm, str] = _TROUBLESHOOT


def label_unmapped_alarm(code: int) -> str:
    """Label for an alarm bit not named in the ALARM Description: its group
    and code, for example ``LIMIT_0x4A``, or ``UNKNOWN_0x70``."""
    return f"{GROUP_LABELS.get(code & 0xF0, 'UNKNOWN')}_0x{code:02X}"


@dataclass(frozen=True, slots=True)
class AlarmSet:
    """Decoded result of ``GetAlarmsState``."""

    raw: bytes
    """The original 16-byte mask, untouched."""

    alarms: tuple[Alarm | int, ...]
    """Active alarm codes (named when known, raw int code otherwise)."""

    def __bool__(self) -> bool:
        return any(b != 0 for b in self.raw)

    def __iter__(self):
        return iter(self.alarms)

    def __contains__(self, item) -> bool:
        return item in self.alarms

    def names(self) -> list[str]:
        """Names for active alarms - useful for logging.

        Unmapped codes are still given a meaningful label based on the
        byte range they sit in (joint-limit, overspeed, lost-step, ...)
        so a student doesn't see a bare 'UNKNOWN_0x4x' for a real
        joint-limit hit on, e.g., a Magician variant whose firmware
        uses a slightly different bit layout.
        """
        out: list[str] = []
        for a in self.alarms:
            if isinstance(a, Alarm):
                out.append(a.name)
            else:
                out.append(label_unmapped_alarm(int(a)))
        return out

    def describe(self) -> list[str]:
        """Backwards-compat alias for :meth:`format`."""
        return self.format()

    def format(self) -> list[str]:
        """Return one ``"{TAG}: {explanation + fix}"`` line per active alarm.

        Used by both the panel banner and the
        :class:`~pydobotlab.errors.DobotKinematicError` message so the student
        sees not just *what* tripped but *what to do about it* - without
        leaving the IDE or the panel window.
        """
        out: list[str] = []
        for a in self.alarms:
            if isinstance(a, Alarm):
                tag = a.name
                tip = _TROUBLESHOOT.get(a, "see the Dobot Magician ALARM Description")
            else:
                code = int(a)
                tag = label_unmapped_alarm(code)
                tip = _BAND_TROUBLESHOOT.get(
                    code & 0xF0, "see the Dobot Magician ALARM Description"
                )
            out.append(f"{tag}: {tip}")
        return out


# Exception raised for each alarm group, keyed by the group's first code.
ERROR_FOR_ALARM_GROUP: dict[int, type[DobotAlarmError]] = {
    0x00: DobotSystemAlarmError,
    0x10: DobotKinematicError,
    0x20: DobotKinematicError,
    0x30: DobotOverspeedError,
    0x40: DobotKinematicError,
    0x50: DobotLostStepError,
}


def alarm_error(active: AlarmSet, heading: str, remedy: str) -> DobotAlarmError:
    """Build the exception for the active alarms.

    The class follows the group of the first active alarm. The message lists
    every active alarm with its fix.
    """
    first_code = int(active.alarms[0]) if active.alarms else -1
    error_class = ERROR_FOR_ALARM_GROUP.get(first_code & 0xF0, DobotAlarmError)
    message = f"{heading}:\n  - " + "\n  - ".join(active.format()) + f"\n{remedy}"
    return error_class(alarms=active.names(), message=message)


def decode_alarms(raw: bytes) -> AlarmSet:
    """Decode the 16-byte alarm bitmask returned by ``GetAlarmsState``."""
    # Pad/truncate defensively - real firmware always sends 16 bytes.
    raw16 = bytes(raw[:16]).ljust(16, b"\x00")
    active: list[Alarm | int] = []
    for byte_index, byte in enumerate(raw16):
        if not byte:
            continue
        for bit in range(8):
            if byte & (1 << bit):
                code = (byte_index * 8) + bit
                try:
                    active.append(Alarm(code))
                except ValueError:
                    active.append(code)
    return AlarmSet(raw=raw16, alarms=tuple(active))


def encode_alarms(alarms: Iterable[Alarm | int]) -> bytes:
    """Inverse of :func:`decode_alarms` - mostly useful for tests."""
    mask = bytearray(16)
    for a in alarms:
        code = int(a)
        mask[code // 8] |= 1 << (code % 8)
    return bytes(mask)
