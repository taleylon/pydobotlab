"""Configuration file: loading, the per-user copy, and use by the rest of the library."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

import pydobotlab.discovery as discovery
from pydobotlab import DobotConfigError, DobotError, Magician
from pydobotlab.broker import DobotBroker, is_broker_reachable
from pydobotlab.config import (
    CONFIG_ENVIRONMENT_VARIABLE,
    DEFAULTS_PATH,
    default_config,
    get_config,
    load_config,
    save_arm_speed,
    saved_arm_speed,
    set_config,
    user_config_path,
)
from pydobotlab.transport import BrokerTransport, SerialTransport


def write_config(directory: Path, text: str) -> Path:
    path = directory / "config.toml"
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


def configure(section: str, **values) -> None:
    config = default_config()
    config[section].update(values)
    set_config(config)


@pytest.fixture
def user_directory(tmp_path, monkeypatch):
    """Point the per-user configuration directory at a temporary directory."""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path


# -- the shipped file and the per-user copy -----------------------------------


def test_shipped_file_holds_every_setting():
    config = default_config()
    assert set(config) == {
        "serial",
        "broker",
        "discovery",
        "panel",
        "motion",
        "simulator",
        "workspace",
        "messages",
    }
    assert (config["broker"]["host"], config["broker"]["port"]) == ("127.0.0.1", 8765)
    assert config["serial"]["baudrate"] == 115200


def test_first_use_creates_the_user_copy(user_directory):
    path = user_config_path()
    assert not path.exists()
    assert load_config() == default_config()
    assert path.read_bytes() == DEFAULTS_PATH.read_bytes()


def test_edits_to_the_user_copy_are_used(user_directory):
    load_config()
    path = user_config_path()
    path.write_text(path.read_text().replace("port = 8765", "port = 9000"))
    assert load_config()["broker"]["port"] == 9000


def test_missing_keys_keep_their_default_value(tmp_path):
    path = write_config(tmp_path, "[panel]\nwatchdog_failures = 5\n")
    config = load_config(path)
    assert config["panel"]["watchdog_failures"] == 5
    assert config["panel"]["pose_hz"] == default_config()["panel"]["pose_hz"]
    assert config["broker"] == default_config()["broker"]


def test_environment_variable_selects_another_file(tmp_path, monkeypatch):
    path = write_config(tmp_path, "[broker]\nport = 9001\n")
    monkeypatch.setenv(CONFIG_ENVIRONMENT_VARIABLE, str(path))
    assert load_config()["broker"]["port"] == 9001


def test_missing_file_named_by_the_environment_variable_is_an_error(tmp_path, monkeypatch):
    monkeypatch.setenv(CONFIG_ENVIRONMENT_VARIABLE, str(tmp_path / "missing.toml"))
    with pytest.raises(DobotConfigError, match="not found"):
        load_config()


def test_unwritable_user_directory_falls_back_to_the_defaults(user_directory, monkeypatch):
    import pydobotlab.config as config_module

    monkeypatch.setattr(config_module, "create_user_config", lambda path: False)
    assert load_config() == default_config()


def test_each_arm_speed_is_saved_by_serial_number(user_directory):
    assert saved_arm_speed("DT1") == 50  # the default speed
    assert save_arm_speed("DT1", 30)
    assert save_arm_speed("DT2", 70.5)
    assert save_arm_speed("DT1", 40)  # replaces its line
    text = user_config_path().read_text(encoding="utf-8")
    assert text.count('"DT1"') == 1
    assert "watchdog_interval = 2.0       # time between connection checks" in text
    set_config(None)
    assert (saved_arm_speed("DT1"), saved_arm_speed("DT2")) == (40, 70.5)
    assert not save_arm_speed("", 10)  # an arm without a serial number uses the default


def test_a_speed_is_saved_in_a_user_copy_from_an_older_version(user_directory):
    path = user_config_path()
    path.parent.mkdir(parents=True)
    path.write_text("[panel]\npose_hz = 20.0\n", encoding="utf-8")
    assert save_arm_speed("DT1", 30)
    config = load_config()
    assert config["motion"]["arms"] == {"DT1": 30}
    assert config["panel"]["pose_hz"] == 20.0


def test_a_speed_saved_by_another_program_is_read(user_directory):
    save_arm_speed("DT1", 30)
    path = user_config_path()
    path.write_text(path.read_text().replace('"DT1" = 30', '"DT1" = 60'), encoding="utf-8")
    assert saved_arm_speed("DT1") == 60


def test_get_config_reads_once_until_it_is_cleared(tmp_path, monkeypatch):
    path = write_config(tmp_path, "[broker]\nport = 9003\n")
    monkeypatch.setenv(CONFIG_ENVIRONMENT_VARIABLE, str(path))
    set_config(None)
    assert get_config()["broker"]["port"] == 9003

    path.write_text("[broker]\nport = 9004\n", encoding="utf-8")
    assert get_config()["broker"]["port"] == 9003
    set_config(None)
    assert get_config()["broker"]["port"] == 9004


# -- invalid files ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("[unknown]\nkey = 1\n", "unknown section \\[unknown\\]"),
        ("[broker]\nprot = 1\n", "unknown key 'prot' in \\[broker\\]"),
        ("[broker]\nport = 'abc'\n", "\\[broker\\] port must be int"),
        ("[broker]\nport = true\n", "\\[broker\\] port must be int"),
        ("[simulator]\narms = 2.5\n", "\\[simulator\\] arms must be int"),
        ("[broker]\nhost = 1\n", "\\[broker\\] host must be str"),
        ("[discovery]\nextra_usb_ids = 3\n", "\\[discovery\\] extra_usb_ids must be list"),
        ("[broker]\nport = \n", "cannot read configuration file"),
        ("broker = 3\n", "unknown section \\[broker\\]"),
    ],
)
def test_invalid_files_are_rejected_with_the_file_name(tmp_path, text, message):
    path = write_config(tmp_path, text)
    with pytest.raises(DobotConfigError, match=message) as raised:
        load_config(path)
    assert str(path) in str(raised.value)


def test_integer_is_accepted_where_the_default_is_a_float(tmp_path):
    path = write_config(tmp_path, "[serial]\ntimeout = 2\n")
    assert load_config(path)["serial"]["timeout"] == 2
    assert issubclass(DobotConfigError, DobotError)


# -- the rest of the library reads the settings -----------------------------------


def test_broker_defaults_come_from_the_configuration():
    configure("broker", host="127.0.0.2", port=9100)
    broker = DobotBroker()
    assert (broker.host, broker.port) == ("127.0.0.2", 9100)

    explicit = DobotBroker(host="127.0.0.3", port=9101)
    assert (explicit.host, explicit.port) == ("127.0.0.3", 9101)


def test_reachability_check_uses_the_configured_port():
    with DobotBroker(port=0) as broker:
        configure("broker", port=broker.port)
        assert is_broker_reachable()


def test_serial_transport_defaults_come_from_the_configuration():
    configure("serial", baudrate=57600, timeout=0.25)
    transport = SerialTransport("COM_TEST")
    assert (transport.baudrate, transport.timeout) == (57600, 0.25)
    assert SerialTransport("COM_TEST", baudrate=9600).baudrate == 9600


def test_broker_transport_and_magician_use_the_configured_broker_address():
    configure("broker", host="127.0.0.4", port=9102)
    transport = BrokerTransport("COM_TEST")
    assert (transport._broker_host, transport._broker_port) == ("127.0.0.4", 9102)

    arm = Magician(port="COM_TEST")
    assert (arm._broker_host, arm._broker_port) == ("127.0.0.4", 9102)
    assert Magician(port="COM_TEST", broker_port=9103)._broker_port == 9103


def test_extra_usb_ids_mark_a_port_as_a_known_adapter(monkeypatch):
    class FakePortInfo:
        device = "COM_TEST"
        description = "Other adapter"
        vid = 0x10C4
        pid = 0xEA60
        serial_number = None

    import serial.tools.list_ports as serial_ports

    monkeypatch.setattr(serial_ports, "comports", lambda: [FakePortInfo()])
    assert not discovery.list_ports()[0].is_known_dobot_adapter

    configure("discovery", extra_usb_ids=[[0x10C4, 0xEA60]])
    assert discovery.list_ports()[0].is_known_dobot_adapter


class RecordingTransport:
    """Stands in for SerialTransport and records the timeout it was given."""

    timeouts: list[float] = []

    def __init__(self, port, timeout):
        RecordingTransport.timeouts.append(timeout)

    def open(self):
        from pydobotlab import DobotConnectionError

        raise DobotConnectionError("closed for test")


def test_discovery_probes_with_the_discovery_timeout(monkeypatch):
    RecordingTransport.timeouts = []
    monkeypatch.setattr(discovery, "SerialTransport", RecordingTransport)
    monkeypatch.setattr(discovery, "list_ports", lambda **_: [discovery.PortInfo("COM_TEST")])
    config = default_config()
    config["serial"]["timeout"] = 3.0
    config["discovery"]["probe_timeout"] = 0.07
    set_config(config)

    assert discovery.is_dobot("COM_TEST") is False
    discovery.discover()
    discovery.is_dobot("COM_TEST", timeout=0.2)
    assert RecordingTransport.timeouts == [0.07, 0.07, 0.2]


# -- workspace bounds -----------------------------------------------------------------


def test_workspace_holds_the_official_maximum_reach():
    assert default_config()["workspace"]["max_radius_mm"] == 320.0


def test_workspace_can_be_narrowed(tmp_path):
    path = write_config(tmp_path, "[workspace]\nmin_radius_mm = 150\nz_max_mm = 100.0\n")
    workspace = load_config(path)["workspace"]
    assert (workspace["min_radius_mm"], workspace["z_max_mm"]) == (150, 100.0)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("max_radius_mm = 400.0", "max_radius_mm must be at most 320.0"),
        ("min_radius_mm = 10.0", "min_radius_mm must be at least 85.0"),
        ("z_min_mm = -300.0", "z_min_mm must be at least -170.0"),
        ("z_max_mm = 400.0", "z_max_mm must be at most 175.0"),
        ("min_radius_mm = 250.0\nmax_radius_mm = 200.0", "min_radius_mm must be below"),
    ],
)
def test_workspace_cannot_be_widened(tmp_path, text, message):
    path = write_config(tmp_path, f"[workspace]\n{text}\n")
    with pytest.raises(DobotConfigError, match=message):
        load_config(path)
