"""Open failures must name the real cause: permission vs busy vs other."""

from __future__ import annotations

import errno

import pytest
import serial

import pydobotlab.discovery as discovery
import pydobotlab.transport as transport_module
from pydobotlab import (
    Dobot,
    DobotConnectionError,
    DobotPermissionError,
    DobotPortInUseError,
)
from pydobotlab.discovery import PortInfo
from pydobotlab.permissions import PortPermissionProblem, describe_permission_problem
from pydobotlab.transport import SerialTransport, classify_open_error, close_open_transports

GROUP_RW = 0o660
OTHERS_ONLY = 0o606


def describe(**overrides):
    values = {
        "group_name": "dialout",
        "device_mode": GROUP_RW,
        "user_name": "alice",
        "group_members": [],
        "user_is_in_group_now": False,
    }
    values.update(overrides)
    return describe_permission_problem("/dev/ttyACM0", **values)


# -- permission diagnosis -----------------------------------------------------


def test_user_not_in_group_is_told_to_add_themselves():
    problem = describe()
    assert problem.reason == "not_in_group"
    assert "not in the 'dialout' group" in problem.message
    assert "usermod -aG dialout" in problem.message


def test_user_added_but_session_old_is_told_to_log_in_again():
    problem = describe(group_members=["alice"])
    assert problem.reason == "needs_new_login"
    assert "Log out and back in" in problem.message
    assert "usermod" not in problem.message


def test_user_in_group_but_still_denied_points_at_device_permissions():
    problem = describe(group_members=["alice"], user_is_in_group_now=True)
    assert problem.reason == "no_group_access"
    assert "ls -l /dev/ttyACM0" in problem.message


def test_group_without_read_write_does_not_suggest_joining_group():
    problem = describe(device_mode=OTHERS_ONLY)
    assert problem.reason == "no_group_access"
    assert "usermod" not in problem.message


# -- open error classification ------------------------------------------------


def no_permission_problem(monkeypatch):
    monkeypatch.setattr(transport_module, "diagnose_port_permission", lambda port: None)


def test_confirmed_permission_problem_beats_any_error_text(monkeypatch):
    problem = PortPermissionProblem("not_in_group", "Permission denied for /dev/x: join dialout")
    monkeypatch.setattr(transport_module, "diagnose_port_permission", lambda port: problem)
    error = serial.SerialException(errno.EAGAIN, "Could not exclusively lock port /dev/x")
    result = classify_open_error("/dev/x", error, posix=True)
    assert isinstance(result, DobotPermissionError)
    assert "join dialout" in str(result)


@pytest.mark.parametrize("code", [errno.EAGAIN, errno.EBUSY])
def test_posix_lock_failure_with_access_is_busy(monkeypatch, code):
    no_permission_problem(monkeypatch)
    result = classify_open_error("/dev/x", serial.SerialException(code, "locked"), posix=True)
    assert isinstance(result, DobotPortInUseError)
    assert str(result) == "port '/dev/x' is busy"


def test_posix_eacces_with_access_is_permission_not_busy(monkeypatch):
    no_permission_problem(monkeypatch)
    result = classify_open_error(
        "/dev/x", serial.SerialException(errno.EACCES, "denied"), posix=True
    )
    assert isinstance(result, DobotPermissionError)
    assert not isinstance(result, DobotPortInUseError)


def test_windows_access_denied_is_busy(monkeypatch):
    no_permission_problem(monkeypatch)
    error = serial.SerialException(
        "could not open port 'COM3': PermissionError(13, 'Access is denied.', None, 5)"
    )
    result = classify_open_error("COM3", error, posix=False)
    assert isinstance(result, DobotPortInUseError)
    assert str(result) == "port 'COM3' is busy"


def test_unrelated_open_failure_stays_generic(monkeypatch):
    no_permission_problem(monkeypatch)
    error = serial.SerialException("could not open port 'COM9': FileNotFoundError(2)")
    result = classify_open_error("COM9", error, posix=False)
    assert type(result) is DobotConnectionError


# -- discovery reasons --------------------------------------------------------


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (DobotPermissionError("denied"), "permission"),
        (DobotPortInUseError("busy"), "busy"),
        (DobotConnectionError("???"), "other"),
    ],
)
def test_discovery_reason_follows_exception_type(monkeypatch, error, reason):
    class RaisingTransport:
        def __init__(self, *args, **kwargs):
            pass

        def open(self):
            raise error

    monkeypatch.setattr(discovery, "SerialTransport", RaisingTransport)
    monkeypatch.setattr(discovery, "list_ports", lambda **kw: [PortInfo(port="/dev/ttyACM0")])
    hits, failures = discovery.discover_with_diagnostics()
    assert hits == []
    assert [(failure.port, failure.reason) for failure in failures] == [("/dev/ttyACM0", reason)]


def test_auto_pick_reports_permission_problem(monkeypatch):
    import pydobotlab.device as device_module

    monkeypatch.setattr(device_module, "find_free_port", lambda **kw: None)
    monkeypatch.setattr(
        discovery,
        "discover_with_diagnostics",
        lambda **kw: (
            [],
            [discovery.ProbeFailure("/dev/ttyACM0", "", "permission", "join the dialout group")],
        ),
    )
    robot = Dobot(via_broker=False, verbose=False)
    with pytest.raises(DobotPermissionError, match="dialout"):
        robot.connect()


# -- connect() logging --------------------------------------------------------


def test_connect_prints_port_on_success(monkeypatch, capsys):
    import pydobotlab.simulator as simulator

    monkeypatch.setattr(simulator, "_INSTALLED", False)
    monkeypatch.setattr(serial, "Serial", serial.Serial)
    simulator.install_simulator(arms=1)
    robot = Dobot("/dev/sim0", via_broker=False)
    try:
        robot.connect()
    finally:
        robot.disconnect()
        simulator.stop_all()
    captured = capsys.readouterr()
    assert "Connected to /dev/sim0" in captured.out
    assert captured.err == ""


def test_connect_prints_reason_on_failure_and_still_raises(monkeypatch, capsys):
    class BusyTransport:
        is_open = False

        def __init__(self, *args):
            pass

        def open(self):
            raise DobotPortInUseError("port '/dev/busy' is busy")

        def close(self):
            pass

    monkeypatch.setattr("pydobotlab.device.SerialTransport", BusyTransport)
    robot = Dobot("/dev/busy", via_broker=False)
    with pytest.raises(DobotPortInUseError):
        robot.connect()
    captured = capsys.readouterr()
    assert "Failed to connect: port '/dev/busy' is busy" in captured.err
    assert captured.out == ""


def test_verbose_false_is_silent(monkeypatch, capsys):
    class BusyTransport:
        def __init__(self, *args):
            pass

        def open(self):
            raise DobotPortInUseError("busy")

        def close(self):
            pass

    monkeypatch.setattr("pydobotlab.device.SerialTransport", BusyTransport)
    with pytest.raises(DobotPortInUseError):
        Dobot("/dev/busy", via_broker=False, verbose=False).connect()
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


# -- leaving without disconnect() ---------------------------------------------


def test_exit_without_disconnect_releases_port(monkeypatch):
    """The atexit hook closes transports a script forgot to disconnect."""

    class Handle:
        is_open = True

        def close(self):
            self.is_open = False

    handle = Handle()
    transport = SerialTransport("/dev/test-forgot-disconnect")
    transport._serial = handle
    transport_module._OPEN_PORTS.add(transport.port)
    transport_module._OPEN_TRANSPORTS.add(transport)

    close_open_transports()

    assert not handle.is_open
    assert not transport_module.is_port_claimed(transport.port)
