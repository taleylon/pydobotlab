"""Alarm text for the control panel.

By default each alarm is one short line: what happened and what to do, in
terms of the panel's buttons. ``pydobotlab-panel --dev`` shows the alarm
names and codes, the library's remedies, and the raw alarm bytes instead.
The text is in ``panel.toml`` (``[alarm_text]``).
"""

from __future__ import annotations

from collections.abc import Iterable

from pydobotlab.alarms import Alarm, decode_alarms, encode_alarms

from .panel_config import PANEL_CONFIG

TEXT = PANEL_CONFIG["alarm_text"]
JOINT_NAMES = dict(enumerate(TEXT["joint_names"], start=1))
SPECIFIC_TEXT = {Alarm[name]: text for name, text in TEXT["alarms"].items()}


def group_line(key: str, joint_number: int) -> str:
    """The group's line for a joint, or the unknown-alarm line for a joint that does not exist."""
    if joint_number not in JOINT_NAMES:
        return TEXT["unknown"]
    return TEXT["groups"][key].format(joint=JOINT_NAMES[joint_number], number=joint_number)


def short_text(code: int) -> str:
    """One line for a user: what happened and what to do."""
    if code in SPECIFIC_TEXT:
        return SPECIFIC_TEXT[Alarm(code)]
    group = code & 0xF0
    if group == 0x00:
        return TEXT["groups"]["system"]
    if group in (0x10, 0x20):
        return TEXT["groups"]["out_of_reach"]
    if group == 0x30:
        return group_line("overspeed", code - 0x30 + 1)
    if 0x40 <= code <= 0x47:  # positive and negative limit of joints 1 to 4, in turn
        key = "positive_limit" if code % 2 == 0 else "negative_limit"
        return group_line(key, (code - 0x40) // 2 + 1)
    if group == 0x40:
        return TEXT["groups"]["joint_limit"]
    if group == 0x50:
        return group_line("lost_step", code - 0x50 + 1)
    return TEXT["unknown"]


def alarm_lines(codes: Iterable[int], developer: bool = False) -> list[str]:
    """Lines describing the active alarms: short ones, or full details for developers."""
    codes = [int(code) for code in codes]
    if developer:
        active = decode_alarms(encode_alarms(codes))
        lines = [
            f"0x{int(alarm):02X} {line}"
            for alarm, line in zip(active.alarms, active.format(), strict=True)
        ]
        return [*lines, f"raw alarm bytes: {active.raw.hex(' ')}"]
    lines: list[str] = []
    for code in codes:
        text = short_text(code)
        if text not in lines:
            lines.append(text)
    return lines
