"""Desktop shortcut and menu entry of the control panel (pydobotlab-panel --create-shortcut)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path, PurePosixPath

import pytest

from pydobotlab.panel import shortcut
from pydobotlab.panel.app import parse_arguments

PANEL_EXEC = '"/usr/bin/python3" -m pydobotlab.panel'


def entry_values(text: str) -> dict[str, str]:
    lines = text.splitlines()
    assert lines[0] == "[Desktop Entry]"
    return dict(line.split("=", 1) for line in lines[1:])


def test_create_shortcut_is_an_option_of_the_panel():
    assert parse_arguments(["--create-shortcut"]).create_shortcut
    assert not parse_arguments([]).create_shortcut


def test_desktop_entry_starts_the_panel_with_the_python_that_created_it():
    values = entry_values(shortcut.desktop_entry(PurePosixPath("/opt/lab env/bin/python3")))
    assert values["Exec"] == '"/opt/lab env/bin/python3" -m pydobotlab.panel'
    assert values["Icon"].replace("\\\\", "\\") == str(shortcut.ICON_PNG)
    assert values["Name"] == "pydobotlab Panel"
    assert values["StartupWMClass"] == "pydobotlab"
    assert values["Terminal"] == "false"


@pytest.mark.parametrize(
    ("argument", "written"),
    [
        ("/usr/bin/python3", '"/usr/bin/python3"'),
        ('/a"b', '"/a\\\\"b"'),  # \" in the command, its backslash doubled in the file
        ("/a$b", '"/a\\\\$b"'),
        ("/a\\b", '"/a\\\\\\\\b"'),  # four backslashes, as the specification says
        ("/a%b", '"/a%%b"'),
    ],
)
def test_exec_arguments_are_quoted_as_the_specification_requires(argument, written):
    assert shortcut.quote_exec_argument(argument) == written


def test_linux_shortcuts_are_a_menu_entry_and_a_trusted_desktop_icon(tmp_path, monkeypatch):
    trusted = []
    monkeypatch.setattr(shortcut, "trust_desktop_icon", trusted.append)
    menu, desktop = tmp_path / "applications", tmp_path / "Desktop"
    desktop.mkdir()
    paths = shortcut.create_linux_shortcuts(PurePosixPath("/usr/bin/python3"), menu, desktop)
    assert paths == [menu / "pydobotlab-panel.desktop", desktop / "pydobotlab-panel.desktop"]
    assert trusted == [paths[1]]
    for path in paths:
        assert entry_values(path.read_text(encoding="utf-8"))["Exec"] == PANEL_EXEC
    if os.name == "posix":
        assert paths[1].stat().st_mode & 0o111  # Ubuntu starts only executable desktop icons


def test_without_a_desktop_folder_only_the_menu_entry_is_made(tmp_path, monkeypatch):
    monkeypatch.setattr(shortcut, "trust_desktop_icon", lambda path: None)
    paths = shortcut.create_linux_shortcuts(PurePosixPath("/usr/bin/python3"), tmp_path, None)
    assert paths == [tmp_path / "pydobotlab-panel.desktop"]


def test_as_root_on_linux_the_menu_entry_is_for_every_user(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(shortcut.sys, "platform", "linux")
    monkeypatch.setattr(shortcut.os, "geteuid", lambda: 0, raising=False)
    monkeypatch.setattr(shortcut, "SYSTEM_MENU_DIRECTORY", tmp_path)
    assert shortcut.main() == 0
    assert (tmp_path / "pydobotlab-panel.desktop").exists()
    assert "Every user finds the panel in the application menu" in capsys.readouterr().out


def test_windows_shortcuts_start_the_panel_without_a_console(tmp_path, monkeypatch):
    calls = []

    def run(command, **options):
        calls.append(options["env"])
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(shortcut.subprocess, "run", run)
    (tmp_path / "pythonw.exe").touch()
    folders = [tmp_path / "Desktop", tmp_path / "Programs"]
    paths = shortcut.create_windows_shortcuts(tmp_path / "python.exe", folders)
    assert paths == [folder / "pydobotlab Panel.lnk" for folder in folders]
    assert [call["PYDOBOTLAB_SHORTCUT"] for call in calls] == [str(path) for path in paths]
    for call in calls:
        assert call["PYDOBOTLAB_TARGET"] == str(tmp_path / "pythonw.exe")
        assert call["PYDOBOTLAB_ARGUMENTS"] == "-m pydobotlab.panel"
        assert call["PYDOBOTLAB_ICON"] == str(shortcut.ICON_ICO)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows shortcut files")
def test_a_windows_shortcut_file_is_created(tmp_path):
    (path,) = shortcut.create_windows_shortcuts(Path(sys.executable), [tmp_path])
    read_back = shortcut.run_powershell(
        "$link = (New-Object -ComObject WScript.Shell).CreateShortcut($env:PYDOBOTLAB_PATH)\n"
        "$link.TargetPath\n$link.Arguments\n$link.IconLocation",
        path=str(path),
    ).splitlines()
    assert path.exists()
    assert Path(read_back[0]) == shortcut.windowless_python(Path(sys.executable))
    assert read_back[1] == "-m pydobotlab.panel"
    assert read_back[2].startswith(str(shortcut.ICON_ICO))
