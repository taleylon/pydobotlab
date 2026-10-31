"""Release notes: the changelog section of a version, as the publish workflow takes it."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

import pydobotlab

SCRIPT = Path(__file__).parent.parent / "scripts" / "changelog_section.py"
spec = importlib.util.spec_from_file_location("changelog_section", SCRIPT)
notes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notes)

CHANGELOG = """# Changelog

## [0.2.1.1] - 2026-10-18

### Added

- A shortcut.

## [0.2.1] - 2026-10-17

### Fixed

- A bug.

[0.2.1.1]: https://example.invalid/compare/v0.2.1...v0.2.1.1
[0.2.1]: https://example.invalid/compare/v0.2...v0.2.1
"""


def test_a_section_is_the_text_under_its_heading():
    assert notes.changelog_section("0.2.1.1", CHANGELOG) == "### Added\n\n- A shortcut.\n"


def test_a_version_is_not_mistaken_for_a_longer_one():
    assert notes.changelog_section("0.2.1", CHANGELOG) == "### Fixed\n\n- A bug.\n"


def test_a_missing_version_is_an_error():
    with pytest.raises(ValueError, match="no section for 0.3"):
        notes.changelog_section("0.3", CHANGELOG)


def test_the_package_version_has_release_notes():
    changelog = notes.CHANGELOG_PATH.read_text(encoding="utf-8")
    assert notes.changelog_section(pydobotlab.__version__, changelog).startswith("### ")
