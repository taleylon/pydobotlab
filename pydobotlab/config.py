"""Settings shared by the whole library.

The settings and their default values are in ``config.toml`` next to this
module. Each user gets a copy of that file on first use (see
:func:`user_config_path`) and can edit it; a key missing from the copy keeps its
default value. ``PYDOBOTLAB_CONFIG`` names a different file to read instead.

The configuration is a dictionary of sections, for example
``get_config()["broker"]["port"]``.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import threading
import tomllib
from pathlib import Path

from .errors import DobotConfigError

DEFAULTS_PATH = Path(__file__).with_name("config.toml")
CONFIG_ENVIRONMENT_VARIABLE = "PYDOBOTLAB_CONFIG"

Config = dict[str, dict[str, object]]  # section name -> key -> value


def user_config_path() -> Path:
    """Per-user file: ``%APPDATA%`` on Windows, ``$XDG_CONFIG_HOME`` or ``~/.config`` elsewhere."""
    if os.name == "nt":
        base_directory = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base_directory = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base_directory / "pydobotlab" / "config.toml"


def read_toml(path: Path) -> Config:
    try:
        with path.open("rb") as file:
            return tomllib.load(file)
    except FileNotFoundError as error:
        raise DobotConfigError(f"configuration file not found: {path}") from error
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise DobotConfigError(f"cannot read configuration file {path}: {error}") from error


def default_config() -> Config:
    """The settings in ``config.toml`` next to this module."""
    return read_toml(DEFAULTS_PATH)


def has_type_of(value: object, default: object) -> bool:
    """An integer may replace a float; otherwise the types must match."""
    if isinstance(default, bool) or isinstance(value, bool):
        return type(value) is type(default)
    if isinstance(default, float):
        return isinstance(value, int | float)
    return isinstance(value, type(default))


def apply_overrides(config: Config, overrides: Config, path: Path) -> Config:
    """Replace values in ``config`` with those in ``overrides``, read from ``path``."""
    for section, values in overrides.items():
        if section not in config or not isinstance(values, dict):
            raise DobotConfigError(f"{path}: unknown section [{section}]")
        for key, value in values.items():
            if key not in config[section]:
                raise DobotConfigError(f"{path}: unknown key {key!r} in [{section}]")
            default = config[section][key]
            if not has_type_of(value, default):
                raise DobotConfigError(
                    f"{path}: [{section}] {key} must be {type(default).__name__}, got {value!r}"
                )
            config[section][key] = value
    return config


def check_workspace_limits(workspace: dict, shipped: dict, path: Path) -> None:
    """The [workspace] values may narrow the shipped area, not widen it."""
    for key in ("min_radius_mm", "z_min_mm"):
        if workspace[key] < shipped[key]:
            raise DobotConfigError(
                f"{path}: [workspace] {key} must be at least {shipped[key]}, got {workspace[key]}"
            )
    for key in ("max_radius_mm", "z_max_mm"):
        if workspace[key] > shipped[key]:
            raise DobotConfigError(
                f"{path}: [workspace] {key} must be at most {shipped[key]}, got {workspace[key]}"
            )
    for low, high in (("min_radius_mm", "max_radius_mm"), ("z_min_mm", "z_max_mm")):
        if workspace[low] >= workspace[high]:
            raise DobotConfigError(f"{path}: [workspace] {low} must be below {high}")


def create_user_config(path: Path) -> bool:
    """Copy the defaults to ``path``. ``False`` if the file cannot be written."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(DEFAULTS_PATH, path)
    except OSError:
        return False
    return True


def load_config(path: str | Path | None = None) -> Config:
    """Read the defaults, then the values in ``path``.

    Without ``path``, reads the file named by ``PYDOBOTLAB_CONFIG``, or the
    per-user file, which is created from the defaults if it does not exist.

    Raises:
        DobotConfigError: the file is missing (when named explicitly), is not
            valid TOML, contains an unknown key or a value of the wrong type,
            or widens the [workspace] area.
    """
    config = default_config()
    if path is None:
        override = os.environ.get(CONFIG_ENVIRONMENT_VARIABLE)
        if override:
            path = Path(override).expanduser()
        else:
            path = user_config_path()
            if not path.exists() and not create_user_config(path):
                return config
    path = Path(path)
    shipped_workspace = dict(config["workspace"])
    apply_overrides(config, read_toml(path), path)
    check_workspace_limits(config["workspace"], shipped_workspace, path)
    return config


_active_config: Config | None = None
_active_config_lock = threading.Lock()


def get_config() -> Config:
    """The active configuration. The file is read on the first call."""
    global _active_config
    with _active_config_lock:
        if _active_config is None:
            _active_config = load_config()
        return _active_config


def set_config(config: Config | None) -> None:
    """Replace the active configuration. ``None`` makes the next call read the file again."""
    global _active_config
    with _active_config_lock:
        _active_config = config


def saved_arm_speed(serial_number: str) -> float:
    """The speed saved for the arm with ``serial_number``, or the default speed.

    The file is read again: a script may have saved a speed since it was last read.
    """
    try:
        config = load_config()
    except DobotConfigError:
        config = get_config()
    else:
        set_config(config)
    speed = config["motion"]["arms"].get(serial_number)
    if isinstance(speed, bool) or not isinstance(speed, int | float):
        return config["motion"]["speed"]
    return speed


def save_arm_speed(serial_number: str, speed: float) -> bool:
    """Save ``speed`` for the arm with ``serial_number`` in ``[motion.arms]`` of the
    configuration file and in the active configuration.

    Only that arm's line is written. ``False`` if the arm has no serial number or
    the file cannot be written.
    """
    if not serial_number:
        return False
    get_config()["motion"]["arms"][serial_number] = speed
    override = os.environ.get(CONFIG_ENVIRONMENT_VARIABLE)
    path = Path(override).expanduser() if override else user_config_path()
    if not path.exists() and not create_user_config(path):
        return False
    try:
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError:
        return False
    entry = f"{json.dumps(serial_number)} = {speed:g}\n"
    key = re.compile(rf'\s*"?{re.escape(serial_number)}"?\s*=')
    headers = [
        index for index, line in enumerate(lines) if line.split("#")[0].strip() == "[motion.arms]"
    ]
    if not headers:
        lines.append(f"\n[motion.arms]\n{entry}")
    else:
        index = headers[0] + 1
        while index < len(lines) and not lines[index].lstrip().startswith("["):
            if key.match(lines[index]):
                lines[index] = entry
                break
            index += 1
        else:
            lines.insert(headers[0] + 1, entry)
    try:
        path.write_text("".join(lines), encoding="utf-8")
    except OSError:
        return False
    return True
