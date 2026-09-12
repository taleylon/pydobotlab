"""Hardware/display-free smoke tests for the panel package.

We can't drive a Qt window in CI without an X server, but we can make sure
the modules at least import without syntax errors when PySide6 is available.
"""

from __future__ import annotations

import importlib

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed; install pydobotlab[gui]")


@pytest.mark.parametrize(
    "modname",
    [
        "pydobotlab.panel",
        "pydobotlab.panel.app",
        "pydobotlab.panel.widgets",
        "pydobotlab.panel.panel",
        "pydobotlab.panel.hub",
    ],
)
def test_panel_module_imports(modname):
    importlib.import_module(modname)


def test_console_script_main_callable():
    from pydobotlab.panel.app import main

    assert callable(main)


def test_main_module_executable_form():
    """``python -m pydobotlab.panel`` must dispatch to app.main."""
    import pydobotlab.panel.__main__ as m
    from pydobotlab.panel.app import main

    assert m.main is main


def test_qss_theme_exists():
    from pathlib import Path

    import pydobotlab.panel

    qss = Path(pydobotlab.panel.__file__).parent / "style.qss"
    assert qss.is_file()
    assert qss.read_text(encoding="utf-8").strip(), "stylesheet should not be empty"
