"""Alarm decoding for the Dobot Magician.

The arm reports active alarms as a 16-byte (128-bit) bitmask returned by
``GetAlarmsState`` (cmd ID 20). Each bit corresponds to one named alarm; the
alarm "ID" is conventionally written in hex from ``0x00`` to ``0x7F`` and
maps to ``(byte_index, bit_within_byte) = (id // 8, id % 8)``.

The list of names below follows the alarm catalogue in the Dobot Magician
API Description (V1.2.3). If a bit is set whose code is not in the catalogue
we still surface it as ``Alarm.UNKNOWN_<id>`` so it isn't silently dropped.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import IntEnum


class Alarm(IntEnum):
    """Named alarm codes. Value = bit position within the 128-bit mask."""

    # ---- Public (system) faults: byte 0 ------------------------------------
    PUBLIC_RESET = 0x00
    PUBLIC_UNDEFINED_INSTRUCTION = 0x01
    PUBLIC_FILE_SYSTEM = 0x02
    PUBLIC_MCU_COMM = 0x03
    PUBLIC_ANGLE_SENSOR_READ = 0x04

    # ---- Planning: byte 2 (codes 0x10–0x17) --------------------------------
    PLAN_INVERSE_RESOLVE = 0x10
    PLAN_INVERSE_LIMIT = 0x11
    PLAN_DATA_REPEAT = 0x12
    PLAN_CURRENT_JOINT_OUT_OF_RANGE = 0x13
    PLAN_MOTION_TARGET_OUT_OF_WORKSPACE = 0x14
    PLAN_IN_SINGULARITY_ZONE = 0x15

    # ---- Kinematic: byte 4 (codes 0x20–0x27) -------------------------------
    KINEMATIC_SINGULARITY = 0x20
    KINEMATIC_TARGET_OUT_OF_WORKSPACE = 0x21
    KINEMATIC_INVERSE_LIMIT = 0x22

    # ---- Overspeed per joint: byte 6 (codes 0x30–0x33) ---------------------
    OVERSPEED_J1 = 0x30
    OVERSPEED_J2 = 0x31
    OVERSPEED_J3 = 0x32
    OVERSPEED_J4 = 0x33

    # ---- Positive joint-limit per joint: byte 8 (codes 0x40–0x43) ----------
    LIMIT_POS_J1 = 0x40
    LIMIT_POS_J2 = 0x41
    LIMIT_POS_J3 = 0x42
    LIMIT_POS_J4 = 0x43

    # ---- Negative joint-limit per joint: byte 10 (codes 0x50–0x53) ---------
    LIMIT_NEG_J1 = 0x50
    LIMIT_NEG_J2 = 0x51
    LIMIT_NEG_J3 = 0x52
    LIMIT_NEG_J4 = 0x53

    # ---- Lost step per joint: byte 12 (codes 0x60–0x63) --------------------
    LOST_STEP_J1 = 0x60
    LOST_STEP_J2 = 0x61
    LOST_STEP_J3 = 0x62
    LOST_STEP_J4 = 0x63

    # ---- Other: byte 14 ----------------------------------------------------
    OTHER_LIMIT_TRIGGERED_J1_J2 = 0x70  # auto-leveling: limit switch hit


# One "{tag}: {explanation + fix}" line per known alarm. Surfaced in both
# the panel banner and the DobotKinematicError message so a student can see
# what went wrong AND what to do about it without leaving the IDE.
_TROUBLESHOOT: dict[Alarm, str] = {
    # System / public faults
    Alarm.PUBLIC_RESET: "the arm was reset - call set_home() before continuing",
    Alarm.PUBLIC_UNDEFINED_INSTRUCTION: "received an unknown command - check firmware version vs. pydobotlab version",
    Alarm.PUBLIC_FILE_SYSTEM: "internal file-system error - power-cycle the arm",
    Alarm.PUBLIC_MCU_COMM: "internal MCU communication failure - power-cycle the arm",
    Alarm.PUBLIC_ANGLE_SENSOR_READ: "couldn't read an angle sensor - check the cables, re-home",
    # Planning
    Alarm.PLAN_INVERSE_RESOLVE: "IK couldn't find a solution - pick a reachable target",
    Alarm.PLAN_INVERSE_LIMIT: "IK solution hits a joint limit - try a different target or R angle",
    Alarm.PLAN_DATA_REPEAT: "duplicate planning data - clear_queue() then retry",
    Alarm.PLAN_CURRENT_JOINT_OUT_OF_RANGE: "current pose is past a joint limit - jog back into range, then clear_alarm()",
    Alarm.PLAN_MOTION_TARGET_OUT_OF_WORKSPACE: "target is outside the arm's reach - pick coordinates inside the workspace",
    Alarm.PLAN_IN_SINGULARITY_ZONE: "trajectory enters a singularity - route via an intermediate waypoint",
    # Kinematic
    Alarm.KINEMATIC_SINGULARITY: "kinematic singularity - route via an intermediate waypoint",
    Alarm.KINEMATIC_TARGET_OUT_OF_WORKSPACE: "target outside the workspace - pick reachable coordinates",
    Alarm.KINEMATIC_INVERSE_LIMIT: "IK hit a joint limit - try a different target or R angle",
    # Overspeed
    Alarm.OVERSPEED_J1: "joint 1 over speed - lower motion_params (e.g. 30, 30)",
    Alarm.OVERSPEED_J2: "joint 2 over speed - lower motion_params (e.g. 30, 30)",
    Alarm.OVERSPEED_J3: "joint 3 over speed - lower motion_params (e.g. 30, 30)",
    Alarm.OVERSPEED_J4: "joint 4 over speed - lower motion_params (e.g. 30, 30)",
    # Positive joint limits
    Alarm.LIMIT_POS_J1: "joint 1 (base) hit positive limit - jog J1 negative, or call set_home()",
    Alarm.LIMIT_POS_J2: "joint 2 (rear arm) hit positive limit - jog J2 negative, or call set_home()",
    Alarm.LIMIT_POS_J3: "joint 3 (forearm) hit positive limit - jog Z down (or J3 negative), or call set_home()",
    Alarm.LIMIT_POS_J4: "joint 4 (R) hit positive limit - jog R negative, or call set_home()",
    # Negative joint limits
    Alarm.LIMIT_NEG_J1: "joint 1 (base) hit negative limit - jog J1 positive, or call set_home()",
    Alarm.LIMIT_NEG_J2: "joint 2 (rear arm) hit negative limit - jog J2 positive, or call set_home()",
    Alarm.LIMIT_NEG_J3: "joint 3 (forearm) hit negative limit - jog Z up (or J3 positive), or call set_home()",
    Alarm.LIMIT_NEG_J4: "joint 4 (R) hit negative limit - jog R positive, or call set_home()",
    # Lost step
    Alarm.LOST_STEP_J1: "joint 1 lost step - re-home the arm to recalibrate",
    Alarm.LOST_STEP_J2: "joint 2 lost step - re-home the arm to recalibrate",
    Alarm.LOST_STEP_J3: "joint 3 lost step - re-home the arm to recalibrate",
    Alarm.LOST_STEP_J4: "joint 4 lost step - re-home the arm to recalibrate",
    # Other
    Alarm.OTHER_LIMIT_TRIGGERED_J1_J2: "auto-leveling limit switch tripped - jog away from it, then clear_alarm()",
}

# Generic per-band fallbacks for unmapped codes (firmware variants, etc.)
_BAND_TROUBLESHOOT: dict[int, str] = {
    0x00: "system fault - power-cycle the arm",
    0x10: "planning failed - pick a reachable target",
    0x20: "kinematic failure - pick a reachable target",
    0x30: "joint over-speed - lower motion_params (try 30, 30)",
    0x40: "joint hit positive limit - jog the joint in the negative direction, or call set_home()",
    0x50: "joint hit negative limit - jog the joint in the positive direction, or call set_home()",
    0x60: "lost step - re-home the arm to recalibrate",
    0x70: "see the firmware manual for details",
}


# Backwards-compat: AlarmSet.describe() used to read this dict directly.
_DESCRIPTIONS: dict[Alarm, str] = _TROUBLESHOOT


def label_unmapped_alarm(code: int) -> str:
    """Human-friendly label for an alarm bit not in the named catalogue.

    Categorises by the byte range so unknown bits in known categories
    (e.g. an extra joint-limit code on a firmware variant) still read as
    'JOINT_LIMIT_POS_0x44' rather than the opaque 'UNKNOWN_0x44'.
    """
    hi = code & 0xF0
    bands = {
        0x00: "SYSTEM",
        0x10: "PLAN",
        0x20: "KINEMATIC",
        0x30: "OVERSPEED",
        0x40: "JOINT_LIMIT_POS",
        0x50: "JOINT_LIMIT_NEG",
        0x60: "LOST_STEP",
        0x70: "OTHER",
    }
    band = bands.get(hi, "UNKNOWN")
    return f"{band}_0x{code:02X}"


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
                tip = _TROUBLESHOOT.get(a, "see the firmware manual for details")
            else:
                code = int(a)
                tag = label_unmapped_alarm(code)
                tip = _BAND_TROUBLESHOOT.get(code & 0xF0, "see the firmware manual for details")
            out.append(f"{tag}: {tip}")
        return out


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
