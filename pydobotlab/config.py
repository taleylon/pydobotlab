"""Settings shared by the whole library.

The settings and their default values are in ``config.toml`` next to this
module. Each user gets a copy of that file on first use (see
:func:`user_config_path`) and can edit it; a key missing from the copy keeps its
default value. ``PYDOBOTLAB_CONFIG`` names a different file to read instead.

The configuration is a dictionary of sections, for example
``get_config()["broker"]["port"]``.
"""

from __future__ import annotations

import os
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
            valid TOML, or contains an unknown key or a value of the wrong type.
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
    return apply_overrides(config, read_toml(path), path)


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
