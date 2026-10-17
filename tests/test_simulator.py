"""Tests for the simulator backend.

Hardware-free end-to-end: install the simulator, then drive a Dobot()
through it the way a student script or the panel would, asserting that
GetPose, set_home, ptp, alarms, and discovery all behave sensibly.
"""

from __future__ import annotations

import math
import time

import pytest

from pydobotlab.alarms import decode_alarms
from pydobotlab.commands import CommandID
from pydobotlab.protocol import pack, unpack, unpack_floats
from pydobotlab.simulator import (
    FOREARM_LENGTH_MM,
    MAXIMUM_REACH_MM,
    REAR_ARM_LENGTH_MM,
    TOOL_OFFSET_MM,
    FakeDobot,
    FakeDobotSerial,
    install_simulator,
    is_reachable,
    is_simulator_installed,
    joint_angles,
    stop_all,
)


@pytest.fixture(autouse=True)
def _isolate_serial(monkeypatch):
    """Patch only for the duration of a test so other suites stay clean."""
    import serial as _serial
    import serial.tools.list_ports as _lp

    import pydobotlab.simulator as sim_mod

    saved_serial = _serial.Serial
    saved_comports = _lp.comports
    saved_installed = sim_mod._INSTALLED
    sim_mod._INSTALLED = False
    yield
    _serial.Serial = saved_serial
    _lp.comports = saved_comports
    sim_mod._INSTALLED = saved_installed
    stop_all()


# ---------------------------------------------------------------------------
# 1. Pure FakeDobot frame round-trips (no Serial / Dobot involved)
# ---------------------------------------------------------------------------


class TestFakeDobotFrameHandling:
    def test_get_pose_returns_8_floats(self):
        bot = FakeDobot(port="/dev/sim-test-1")
        try:
            req = pack(CommandID.GET_POSE, 0)
            resp = unpack(bot.handle_frame(req))
            assert resp.cmd_id == CommandID.GET_POSE
            assert len(resp.params) == 32
            x, y, z, r, j1, j2, j3, j4 = unpack_floats(resp.params)
            # Defaults: home pose
            assert (x, y, z, r) == (200.0, 0.0, 50.0, 0.0)
        finally:
            bot.stop()

    def test_set_home_returns_queued_index(self):
        bot = FakeDobot(port="/dev/sim-test-2")
        try:
            req = pack(CommandID.SET_HOME_CMD, 0b11, b"\x00\x00\x00\x00")
            resp = unpack(bot.handle_frame(req))
            assert resp.cmd_id == CommandID.SET_HOME_CMD
            import struct

            (idx,) = struct.unpack("<Q", resp.params[:8])
            assert idx == 1
        finally:
            bot.stop()

    def test_clear_alarm_succeeds_and_alarms_read_empty(self):
        bot = FakeDobot(port="/dev/sim-test-3")
        try:
            # set/clear (write side)
            bot.handle_frame(pack(CommandID.CLEAR_ALL_ALARMS_STATE, 0b01))
            # read alarms (read side, same id)
            resp = unpack(bot.handle_frame(pack(CommandID.GET_ALARMS_STATE, 0)))
            assert resp.params == b"\x00" * 16
        finally:
            bot.stop()

    def test_ptp_animates_pose_toward_target(self):
        bot = FakeDobot(port="/dev/sim-test-4", speed_mm_per_s=500.0, tick_hz=60.0)
        try:
            import struct

            # MOVL_XYZ to (300, 0, 50, 0) - far from home, so we'll see motion
            params = bytes([2]) + struct.pack("<4f", 300.0, 0.0, 50.0, 0.0)
            bot.handle_frame(pack(CommandID.SET_PTP_CMD, 0b11, params))
            # Sample pose immediately, then after ~0.4s - expect intermediate
            r0 = unpack(bot.handle_frame(pack(CommandID.GET_POSE, 0)))
            x0, *_ = unpack_floats(r0.params[:32])
            time.sleep(0.4)
            r1 = unpack(bot.handle_frame(pack(CommandID.GET_POSE, 0)))
            x1, *_ = unpack_floats(r1.params[:32])
            # x should have grown toward 300 (we started at 200)
            assert x1 > x0, f"pose did not animate: x0={x0} x1={x1}"
            assert 200.0 <= x1 <= 300.0
        finally:
            bot.stop()


# ---------------------------------------------------------------------------
# 2. install_simulator() patches serial + comports correctly
# ---------------------------------------------------------------------------


class TestInstallSimulator:
    def test_returns_requested_number_of_ports(self):
        ports = install_simulator(arms=3)
        assert ports == ["/dev/sim0", "/dev/sim1", "/dev/sim2"]
        assert is_simulator_installed()

    def test_serial_open_yields_fake(self):
        install_simulator(arms=1)
        import serial as _serial

        assert _serial.Serial is FakeDobotSerial

    def test_comports_returns_only_simulated_ports(self):
        install_simulator(arms=2)
        from serial.tools import list_ports as _lp

        ports = list(_lp.comports())
        assert {p.device for p in ports} == {"/dev/sim0", "/dev/sim1"}
        # All should look like the known CH340 adapter
        for p in ports:
            assert (p.vid, p.pid) == (0x1A86, 0x7523)

    def test_dobot_round_trip_via_simulator(self):
        install_simulator(arms=1)
        from pydobotlab import Dobot

        bot = Dobot("/dev/sim0", via_broker=False, auto_start_queue=False)
        bot.connect()
        try:
            x, y, z, r, joints = bot.get_pose()
            assert (x, y, z, r) == (200.0, 0.0, 50.0, 0.0)
            assert joints == [0.0, 0.0, 0.0, 0.0]
            sn = bot.get_device_serial_number()
            assert sn == "SIM-MAGICIAN"
            # Alarms should be empty
            assert not bot.get_alarms()
        finally:
            bot.disconnect()

    def test_discovery_finds_simulated_arms(self):
        install_simulator(arms=2)
        from pydobotlab import Discovery

        # list_ports sees them
        ports = Discovery.list_ports()
        sim_ports = sorted(p.port for p in ports if p.port.startswith("/dev/sim"))
        assert sim_ports == ["/dev/sim0", "/dev/sim1"]
        # discover() probes each one and confirms via GetDeviceSN
        hits = Discovery.discover()
        assert {h.port for h in hits} == {"/dev/sim0", "/dev/sim1"}
        for h in hits:
            assert h.serial_number == "SIM-MAGICIAN"


def test_speed_set_by_one_client_is_used_by_another_through_the_broker():
    """The panel and a script share one arm, so they share its speed."""
    from pydobotlab import Magician
    from pydobotlab.broker import DobotBroker

    install_simulator(arms=1)
    with DobotBroker(port=0) as broker:
        options = {"via_broker": True, "broker_port": broker.port, "verbose": False}
        with (
            Magician("/dev/sim0", **options) as panel_side,
            Magician("/dev/sim0", **options) as script,
        ):
            panel_side.motion_params = (30, 30)
            panel_side.set_jog_common_params(30, 30)
            assert script.motion_params == (30.0, 30.0)
            assert script.get_jog_common_params() == (30.0, 30.0)

            script.motion_params = (80, 80)
            assert panel_side.get_arm_speed_ratio(1) == 80.0


def test_a_script_connects_through_the_running_panel():
    from pydobotlab import Magician
    from pydobotlab.broker import DobotBroker
    from pydobotlab.transport import BrokerTransport

    install_simulator(arms=1)
    with DobotBroker(port=0) as broker:
        with Magician("/dev/sim0", broker_port=broker.port, verbose=False) as script:
            assert isinstance(script._transport, BrokerTransport)
            assert broker.client_count() == 1


def test_a_script_needs_the_panel_unless_require_panel_is_false(monkeypatch):
    import pydobotlab.broker as broker_module
    from pydobotlab import DobotConnectionError, Magician
    from pydobotlab.transport import SerialTransport

    install_simulator(arms=1)
    monkeypatch.setattr(broker_module, "is_broker_reachable", lambda *args, **kwargs: False)
    with pytest.raises(DobotConnectionError, match="panel is not running"):
        Magician("/dev/sim0", require_panel=True, verbose=False).connect()

    with Magician("/dev/sim0", require_panel=False, verbose=False) as script:
        assert isinstance(script._transport, SerialTransport)


@pytest.mark.parametrize("panel_installed", [True, False])
def test_the_panel_is_required_by_default_only_where_it_is_installed(monkeypatch, panel_installed):
    import pydobotlab.broker as broker_module
    import pydobotlab.device as device_module
    from pydobotlab import DobotConnectionError, Magician
    from pydobotlab.transport import SerialTransport

    install_simulator(arms=1)
    monkeypatch.setattr(broker_module, "is_broker_reachable", lambda *args, **kwargs: False)
    monkeypatch.setattr(device_module, "is_panel_installed", lambda: panel_installed)
    script = Magician("/dev/sim0", verbose=False)
    if panel_installed:
        with pytest.raises(DobotConnectionError, match="panel is not running"):
            script.connect()
    else:
        with script:
            assert isinstance(script._transport, SerialTransport)


# ---------------------------------------------------------------------------
# 3. Workspace follows the real arm's joint ranges and arm lengths
# ---------------------------------------------------------------------------


def tool_position(base: float, rear_arm: float, forearm: float) -> tuple[float, float, float]:
    """Forward kinematics, the inverse of joint_angles."""
    radius = (
        REAR_ARM_LENGTH_MM * math.sin(math.radians(rear_arm))
        + FOREARM_LENGTH_MM * math.cos(math.radians(forearm))
        + TOOL_OFFSET_MM
    )
    height = REAR_ARM_LENGTH_MM * math.cos(math.radians(rear_arm)) - FOREARM_LENGTH_MM * math.sin(
        math.radians(forearm)
    )
    return (
        radius * math.cos(math.radians(base)),
        radius * math.sin(math.radians(base)),
        height,
    )


@pytest.mark.parametrize(
    "target",
    [(200, 0, 50), (150, 120, 50), (200, 80, -30), (230, 0, -45), (300, 0, 50), (0, 200, 0)],
)
def test_reachable_targets_have_joint_angles_within_range(target):
    angles = joint_angles(*target)
    assert angles is not None
    base, rear_arm, forearm = angles
    assert -90 <= base <= 90 and 0 <= rear_arm <= 85 and -10 <= forearm <= 90
    assert tool_position(*angles) == pytest.approx(target, abs=1e-6)


def test_farthest_point_is_the_official_maximum_reach():
    height_at_full_reach = REAR_ARM_LENGTH_MM * math.cos(math.radians(85))
    assert is_reachable(MAXIMUM_REACH_MM, 0, height_at_full_reach)
    assert not is_reachable(MAXIMUM_REACH_MM + 1, 0, height_at_full_reach)


@pytest.mark.parametrize(
    "target",
    [
        (-200, 0, 50),  # behind the base: base range is -90..+90 degrees
        (300, 0, 150),  # far and high
        (90, 0, 150),  # close and high
        (200, 0, -200),  # below the lowest reach
        (500, 500, 0),
    ],
)
def test_unreachable_targets(target):
    assert not is_reachable(*target)


def test_unreachable_target_sets_the_workspace_alarm():
    arm = FakeDobot("/dev/sim-workspace")
    try:
        arm.set_motion_target(-200, 0, 50, 0)
        assert decode_alarms(bytes(arm._alarms)).names() == ["PLAN_INVERSE_CALCULATION"]
    finally:
        arm.stop()


def test_jump_parameters_have_defaults_before_first_write():
    from pydobotlab import Dobot

    install_simulator(arms=1)
    with Dobot("/dev/sim0", via_broker=False) as robot:
        assert robot.jump_params == (100.0, 20.0)
        robot.jump_params = (90.0, 30.0)
        assert robot.jump_params == (90.0, 30.0)
