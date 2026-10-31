"""Shared fixtures."""

from __future__ import annotations

import pytest

from pydobotlab.config import CONFIG_ENVIRONMENT_VARIABLE, default_config, set_config


@pytest.fixture(autouse=True)
def default_configuration(monkeypatch, tmp_path):
    """Run every test with the shipped defaults, whatever is on the developer's machine,
    and save settings (the arms' speeds) in a temporary per-user file."""
    monkeypatch.delenv(CONFIG_ENVIRONMENT_VARIABLE, raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    set_config(default_config())
    yield
    set_config(None)
