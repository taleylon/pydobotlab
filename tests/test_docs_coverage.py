"""The API reference in docs/api must document every public name."""

from __future__ import annotations

import re
from dataclasses import fields
from pathlib import Path

import pytest

import pydobotlab
from pydobotlab import (
    AlarmSet,
    DiscoveredDobot,
    Discovery,
    EndEffectorType,
    IOFunction,
    JOGCmd,
    JogMode,
    Magician,
    PortInfo,
    Pose,
    ProbeFailure,
    PTPMode,
)
from pydobotlab.broker import DobotBroker
from pydobotlab.protocol import Frame

API_DOCS = Path(__file__).parent.parent / "docs" / "api"

pytestmark = pytest.mark.skipif(not API_DOCS.is_dir(), reason="docs/api not available")

DEPRECATED_MAGICIAN_ALIASES = {
    "home",
    "clear_alarms",
    "wait_seconds",
    "get_pose_l",
    "get_slideway_pose",
}

INLINE_CODE = re.compile(r"`([^`\n]+)`")
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
HEADING_ID = re.compile(r"^#+ .*\{#([a-z0-9_-]+)\}\s*$", re.MULTILINE)


def public_members(cls: type) -> set[str]:
    return {name for name in vars(cls) if not name.startswith("_")}


def read_api_docs() -> str:
    return "\n".join(page.read_text(encoding="utf-8") for page in sorted(API_DOCS.glob("*.md")))


API_TEXT = read_api_docs() if API_DOCS.is_dir() else ""
DOCUMENTED_IDENTIFIERS = {
    identifier for code in INLINE_CODE.findall(API_TEXT) for identifier in IDENTIFIER.findall(code)
}
HEADING_IDS = set(HEADING_ID.findall(API_TEXT))

REQUIRED_NAMES = sorted(
    {*pydobotlab.__all__, "__version__"}
    | set().union(
        *(public_members(cls) for cls in (Magician, Pose, AlarmSet, Frame, DobotBroker, Discovery))
    )
    | {field.name for cls in (PortInfo, DiscoveredDobot, ProbeFailure) for field in fields(cls)}
    | {
        member.name
        for enum in (PTPMode, JogMode, JOGCmd, EndEffectorType, IOFunction)
        for member in enum
    }
    | {
        "is_broker_reachable",
        "list_broker_ports",
        "install_simulator",
        "is_simulator_installed",
        "stop_all",
    }
)

MAGICIAN_METHODS = sorted(
    name
    for name, value in vars(Magician).items()
    if not name.startswith("_")
    and name not in DEPRECATED_MAGICIAN_ALIASES
    and (callable(value) or isinstance(value, property))
)


@pytest.mark.parametrize("name", REQUIRED_NAMES)
def test_public_name_is_documented(name):
    assert name in DOCUMENTED_IDENTIFIERS, f"{name!r} does not appear in docs/api"


@pytest.mark.parametrize("name", MAGICIAN_METHODS)
def test_magician_method_has_entry(name):
    assert name in HEADING_IDS, f"no heading with id {{#{name}}} in docs/api"
