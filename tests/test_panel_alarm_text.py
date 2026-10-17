"""Alarm text of the control panel: short by default, full details for developers."""

from __future__ import annotations

import pytest

from pydobotlab.alarms import Alarm
from pydobotlab.panel.alarm_text import alarm_lines, short_text
from pydobotlab.panel.panel_config import PANEL_CONFIG

UNKNOWN = PANEL_CONFIG["alarm_text"]["unknown"]


@pytest.mark.parametrize("alarm", list(Alarm), ids=lambda alarm: alarm.name)
def test_every_alarm_has_a_short_line_without_codes(alarm):
    text = short_text(int(alarm))
    assert text.endswith(".")
    assert text != UNKNOWN
    assert alarm.name not in text
    assert "0x" not in text and "{" not in text


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (0x40, "The base (J1) reached its limit. Jog J1- to move it back."),
        (0x43, "The rear arm (J2) reached its limit. Jog J2+ to move it back."),
        (0x44, "The forearm (J3) reached its limit. Jog J3- to move it back."),
        (0x47, "The end-effector rotation (J4) reached its limit. Jog J4+ to move it back."),
        (0x48, "The arm is stretched to its limit. Jog back the way it came."),
        (0x31, "The rear arm (J2) moved too fast. Lower the speed, then press Clear Alarm."),
        (0x52, "The forearm (J3) lost steps. Press Home."),
        (0x11, "The target is out of reach. Press Clear Alarm and choose a reachable target."),
        (0x00, "The arm was reset. Press Clear Alarm."),
        (0x4A, "A joint reached its limit. Jog it back the other way."),
        (0x7F, UNKNOWN),
    ],
)
def test_short_lines(code, expected):
    assert short_text(code) == expected


def test_alarms_with_the_same_line_are_listed_once():
    assert alarm_lines([0x11, 0x21]) == [
        "The target is out of reach. Press Clear Alarm and choose a reachable target."
    ]


def test_developer_lines_show_names_codes_remedies_and_raw_bytes():
    lines = alarm_lines([0x44], developer=True)
    assert lines[0].startswith("0x44 LIMIT_POS_J3: joint 3 (forearm) at its positive limit")
    assert lines[-1] == "raw alarm bytes: " + " ".join(["00"] * 8 + ["10"] + ["00"] * 7)
