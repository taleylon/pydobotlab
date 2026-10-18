"""Desktop shortcut and menu entry for the control panel.

``pydobotlab-panel --create-shortcut`` runs :func:`main`. The shortcuts start
the panel with the Python interpreter that created them, so they work from a
virtual environment and from a system-wide installation. No Qt is needed here.

- Windows: a shortcut on the desktop and in the Start menu.
- Linux: a desktop icon and an application menu entry. As root, a menu entry
  for every user instead.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path, PurePath

from .panel_config import PANEL_CONFIG

SHORTCUT = PANEL_CONFIG["shortcut"]
MESSAGES = SHORTCUT["messages"]
ICON_PNG = Path(__file__).with_name("icon.png")
ICON_ICO = Path(__file__).with_name("icon.ico")
PANEL_ARGUMENTS = "-m pydobotlab.panel"
SYSTEM_MENU_DIRECTORY = Path("/usr/local/share/applications")

# Each value is passed in an environment variable, so paths need no quoting.
WINDOWS_FOLDERS_SCRIPT = """
[Environment]::GetFolderPath('Desktop')
[Environment]::GetFolderPath('Programs')
"""
WINDOWS_SHORTCUT_SCRIPT = """
$link = (New-Object -ComObject WScript.Shell).CreateShortcut($env:PYDOBOTLAB_SHORTCUT)
$link.TargetPath = $env:PYDOBOTLAB_TARGET
$link.Arguments = $env:PYDOBOTLAB_ARGUMENTS
$link.IconLocation = $env:PYDOBOTLAB_ICON
$link.Description = $env:PYDOBOTLAB_COMMENT
$link.WorkingDirectory = $env:USERPROFILE
$link.Save()
"""


# ---- Linux ---------------------------------------------------------------------


def quote_exec_argument(argument: str) -> str:
    """Quote an argument of the ``Exec`` key as the Desktop Entry Specification requires."""
    escaped = "".join(
        "\\" + character if character in '"`$\\' else character for character in argument
    )
    # The string escapes of the file apply before the quoting, so each backslash is doubled again.
    return '"' + escaped.replace("\\", "\\\\").replace("%", "%%") + '"'


def desktop_entry(python: PurePath) -> str:
    """The ``.desktop`` file that starts the panel with ``python``."""
    icon = str(ICON_PNG).replace("\\", "\\\\")
    lines = [
        "[Desktop Entry]",
        "Type=Application",
        f"Name={SHORTCUT['name']}",
        f"Comment={SHORTCUT['comment']}",
        f"Exec={quote_exec_argument(str(python))} {PANEL_ARGUMENTS}",
        f"Icon={icon}",
        "Terminal=false",
        f"Categories={SHORTCUT['categories']}",
        f"StartupWMClass={SHORTCUT['application_name']}",
    ]
    return "\n".join(lines) + "\n"


def write_desktop_entry(directory: Path, python: PurePath, *, executable: bool = False) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{SHORTCUT['desktop_id']}.desktop"
    path.write_text(desktop_entry(python), encoding="utf-8")
    path.chmod(0o755 if executable else 0o644)
    return path


def user_menu_directory() -> Path:
    data_home = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(data_home) / "applications"


def user_desktop_directory() -> Path | None:
    """The user's desktop folder, which can have a translated name, or ``None``."""
    try:
        result = subprocess.run(
            ["xdg-user-dir", "DESKTOP"], capture_output=True, text=True, check=True
        )
        desktop = Path(result.stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        desktop = Path.home() / "Desktop"
    # xdg-user-dir answers the home folder when no desktop folder is set.
    if desktop == Path.home() or not desktop.is_dir():
        return None
    return desktop


def trust_desktop_icon(path: Path) -> None:
    """Let Ubuntu's desktop start the icon without asking first. Not every desktop has gio."""
    try:
        subprocess.run(
            ["gio", "set", str(path), "metadata::trusted", "true"],
            capture_output=True,
            check=False,
        )
    except OSError:
        pass


def create_linux_shortcuts(
    python: PurePath, menu_directory: Path, desktop_directory: Path | None
) -> list[Path]:
    paths = [write_desktop_entry(menu_directory, python)]
    if desktop_directory is not None:
        desktop_icon = write_desktop_entry(desktop_directory, python, executable=True)
        trust_desktop_icon(desktop_icon)
        paths.append(desktop_icon)
    return paths


# ---- Windows -------------------------------------------------------------------


def run_powershell(script: str, **variables: str) -> str:
    """Run ``script``; each variable is ``$env:PYDOBOTLAB_<NAME>`` in it. Returns the output."""
    environment = dict(os.environ)
    environment.update({f"PYDOBOTLAB_{name.upper()}": value for name, value in variables.items()})
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        env=environment,
    )
    if result.returncode != 0:
        raise OSError(result.stderr.strip() or f"PowerShell exited with {result.returncode}")
    return result.stdout


def windowless_python(python: Path) -> Path:
    """``pythonw.exe`` next to ``python.exe``: it starts the panel without a console window."""
    candidate = python.with_name("pythonw.exe")
    return candidate if candidate.exists() else python


def windows_shortcut_folders() -> list[Path]:
    """The desktop and the Start menu's Programs folder of the user."""
    output = run_powershell(WINDOWS_FOLDERS_SCRIPT)
    return [Path(line.strip()) for line in output.splitlines() if line.strip()]


def create_windows_shortcuts(python: Path, folders: list[Path]) -> list[Path]:
    paths = []
    for folder in folders:
        path = folder / f"{SHORTCUT['name']}.lnk"
        run_powershell(
            WINDOWS_SHORTCUT_SCRIPT,
            shortcut=str(path),
            target=str(windowless_python(python)),
            arguments=PANEL_ARGUMENTS,
            icon=str(ICON_ICO),
            comment=SHORTCUT["comment"],
        )
        paths.append(path)
    return paths


# ---- Command -------------------------------------------------------------------


def main() -> int:
    """Create the shortcuts for this system and print where they are."""
    python = Path(sys.executable)
    is_linux = sys.platform.startswith("linux")
    if sys.platform != "win32" and not is_linux:
        print(MESSAGES["not_supported"], file=sys.stderr)
        return 1
    for_all_users = is_linux and os.geteuid() == 0
    try:
        if sys.platform == "win32":
            paths = create_windows_shortcuts(python, windows_shortcut_folders())
        elif for_all_users:
            paths = [write_desktop_entry(SYSTEM_MENU_DIRECTORY, python)]
        else:
            paths = create_linux_shortcuts(python, user_menu_directory(), user_desktop_directory())
    except OSError as error:
        print(MESSAGES["failed"].format(error=error), file=sys.stderr)
        return 1
    for path in paths:
        print(MESSAGES["created"].format(path=path))
    if for_all_users:
        print(MESSAGES["all_users"])
    elif is_linux and len(paths) > 1:
        print(MESSAGES["allow_launching"])
    return 0
