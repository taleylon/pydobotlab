"""Tests for the in-process port registry and the post-refactor surface.

These never touch real serial hardware — they poke the module-level set
through the public functions and assert behaviour. Also asserts the API
shape after the discovery refactor (methods removed from Dobot, moved to
pydobotlab.discovery).
"""

from __future__ import annotations

import pytest

from pydobotlab import Discovery, Dobot, DobotConnectionError, DobotPortInUseError
from pydobotlab.transport import (
    _OPEN_PORTS,
    SerialTransport,
    claimed_ports,
    is_port_claimed,
)


@pytest.fixture(autouse=True)
def _isolate_registry():
    snapshot = set(_OPEN_PORTS)
    yield
    _OPEN_PORTS.clear()
    _OPEN_PORTS.update(snapshot)


# ---------------------------------------------------------------------------
# Registry behaviour
# ---------------------------------------------------------------------------


def test_empty_by_default():
    _OPEN_PORTS.clear()
    assert claimed_ports() == []
    assert not is_port_claimed("/dev/ttyUSB0")


def test_registry_reports_claimed_ports():
    _OPEN_PORTS.clear()
    _OPEN_PORTS.add("/dev/ttyUSB0")
    _OPEN_PORTS.add("/dev/ttyUSB1")
    assert is_port_claimed("/dev/ttyUSB0")
    assert claimed_ports() == ["/dev/ttyUSB0", "/dev/ttyUSB1"]


def test_double_open_raises_port_in_use_error(monkeypatch):
    class _FakeSerial:
        is_open = True

        def __init__(self, **kwargs):
            pass

        def open(self):
            self.is_open = True

        def reset_input_buffer(self):
            pass

        def reset_output_buffer(self):
            pass

        def close(self):
            self.is_open = False

    import pydobotlab.transport as transport_mod

    monkeypatch.setattr(transport_mod.serial, "Serial", _FakeSerial)

    t1 = SerialTransport("/dev/fake0")
    t1.open()
    try:
        assert is_port_claimed("/dev/fake0")
        t2 = SerialTransport("/dev/fake0")
        with pytest.raises(DobotPortInUseError):
            t2.open()
    finally:
        t1.close()
    assert not is_port_claimed("/dev/fake0")


def test_close_releases_registry(monkeypatch):
    class _FakeSerial:
        is_open = True

        def __init__(self, **kwargs):
            pass

        def open(self):
            self.is_open = True

        def reset_input_buffer(self):
            pass

        def reset_output_buffer(self):
            pass

        def close(self):
            self.is_open = False

    import pydobotlab.transport as transport_mod

    monkeypatch.setattr(transport_mod.serial, "Serial", _FakeSerial)

    t = SerialTransport("/dev/fake1")
    t.open()
    assert is_port_claimed("/dev/fake1")
    t.close()
    assert not is_port_claimed("/dev/fake1")


def test_open_failure_releases_registry(monkeypatch):
    import pydobotlab.transport as transport_mod

    def _exploding_serial(**kwargs):
        raise transport_mod.serial.SerialException("simulated open failure")

    monkeypatch.setattr(transport_mod.serial, "Serial", _exploding_serial)

    t = SerialTransport("/dev/fake2")
    with pytest.raises(DobotConnectionError):
        t.open()
    assert not is_port_claimed("/dev/fake2")


def test_exclusive_lock_conflict_classified_as_port_in_use(monkeypatch):
    import pydobotlab.transport as transport_mod

    def _busy(**kwargs):
        raise transport_mod.serial.SerialException("Could not exclusively lock port /dev/foo")

    monkeypatch.setattr(transport_mod.serial, "Serial", _busy)
    t = SerialTransport("/dev/fake3")
    with pytest.raises(DobotPortInUseError):
        t.open()


# ---------------------------------------------------------------------------
# Post-refactor API shape
# ---------------------------------------------------------------------------


def test_discovery_methods_are_not_on_dobot_class():
    """After the refactor, discovery lives in pydobotlab.discovery only."""
    for attr in ("list_ports", "discover", "is_port_in_use", "is_dobot_on", "auto", "open_many"):
        assert not hasattr(Dobot, attr), (
            f"Dobot.{attr} should have been removed; discovery belongs in pydobotlab.discovery"
        )


def test_discovery_namespace_class_exposes_all_functions():
    for name in ("list_ports", "discover", "is_dobot", "find_free_port", "is_port_in_use"):
        assert callable(getattr(Discovery, name)), name


def test_dobot_constructor_defaults_port_to_none():
    """Auto-pick is the default — no positional port argument required."""
    bot = Dobot()
    assert bot.port is None
    assert not bot.is_open


def test_dobot_explicit_port_is_remembered_before_connect():
    bot = Dobot("/dev/ttyUSB0")
    assert bot.port == "/dev/ttyUSB0"
    assert not bot.is_open


def test_auto_pick_raises_clean_error_when_no_dobot_found(monkeypatch):
    """Dobot() with no reachable arms should fail with DobotConnectionError."""
    import pydobotlab.discovery as discovery_mod

    monkeypatch.setattr(discovery_mod, "find_free_port", lambda **kw: None)
    # device.py imports find_free_port directly, monkeypatch it there too
    import pydobotlab.device as device_mod

    monkeypatch.setattr(device_mod, "find_free_port", lambda **kw: None)

    bot = Dobot()
    with pytest.raises(DobotConnectionError):
        bot.connect()


def test_known_dobot_usb_ids_only_contains_ch340():
    """We only ship verified VID/PIDs. Currently CH340 is the only one."""
    from pydobotlab.discovery import KNOWN_DOBOT_USB_IDS

    assert (0x1A86, 0x7523) in KNOWN_DOBOT_USB_IDS
    # No speculative entries should be present out of the box.
    speculative = {(0x1A86, 0x55D4), (0x10C4, 0xEA60)}
    assert not (KNOWN_DOBOT_USB_IDS & speculative), (
        "speculative CH9102 / CP210x entries should not be in the default set"
    )
