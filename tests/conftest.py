"""Shared fixtures."""

from __future__ import annotations

import pytest

from pydobotlab.config import CONFIG_ENVIRONMENT_VARIABLE, default_config, set_config


@pytest.fixture(autouse=True)
def default_configuration(monkeypatch):
    """Run every test with the shipped defaults, whatever is on the developer's machine."""
    monkeypatch.delenv(CONFIG_ENVIRONMENT_VARIABLE, raising=False)
    set_config(default_config())
    yield
    set_config(None)
