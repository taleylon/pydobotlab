"""DobotLab behavior: setters wait for the arm, and arm alarms stop the program.

Runs against the simulator, which, like the real arm, executes its queue in
order and does not run it while an alarm is active.
"""

from __future__ import annotations

import struct
import time
from unittest.mock import Mock

import pytest

from pydobotlab import (
    Alarm,
    CommandID,
    DobotAlarmError,
    DobotKinematicError,
    DobotLostStepError,
    DobotOverspeedError,
    DobotSystemAlarmError,
    Magician,
)
from pydobotlab.alarms import alarm_error, decode_alarms, encode_alarms
from pydobotlab.protocol import pack, unpack
from pydobotlab.simulator import FakeDobot, install_simulator, stop_all

UNREACHABLE = {"x": -200, "y": 0, "z": 50, "r": 0}  # behind the base


@pytest.fixture
def robot():
    """A connected arm on a fresh simulator, at full speed to keep tests short."""
    import serial as serial_module
    import serial.tools.list_ports as list_ports

    import pydobotlab.simulator as simulator

    saved = (serial_module.Serial, list_ports.comports, simulator._INSTALLED)
    simulator._INSTALLED = False
    install_simulator(arms=1)
    arm = Magician("/dev/sim0", via_broker=False, verbose=False)
    arm.connect()
    arm.motion_params = 100, 100
    yield arm
    arm.disconnect()
    stop_all()
    serial_module.Serial, list_ports.comports, simulator._INSTALLED = saved


def position(arm: Magician) -> tuple[float, float, float]:
    pose = arm.get_pose()
    return round(pose.x, 3), round(pose.y, 3), round(pose.z, 3)


# -- setters wait and return True -------------------------------------------------


def test_motion_params_saves_the_speed_of_this_arm(robot):
    from pydobotlab.config import saved_arm_speed

    robot.motion_params = 40, 20
    assert robot.motion_params == (40, 20)
    assert saved_arm_speed(robot.get_device_serial_number()) == 40  # the panel sets it


def test_ptp_returns_true_after_the_move_has_ended(robot):
    assert robot.ptp(mode=1, x=250, y=30, z=20, r=0) is True
    assert position(robot) == (250, 30, 20)


def test_pick_and_place_runs_in_order_without_wait_calls(robot):
    robot.ptp(mode=1, x=220, y=80, z=0, r=0)
    assert robot.set_endeffector_suctioncup(enable=True, on=True) is True
    assert position(robot) == (220, 80, 0)
    robot.ptp(mode=1, x=220, y=-80, z=0, r=0)
    robot.set_endeffector_suctioncup(enable=True, on=False)
    assert position(robot) == (220, -80, 0)


def test_wait_pauses_the_program(robot):
    start = time.monotonic()
    assert robot.wait(0.3) is True
    assert time.monotonic() - start >= 0.3


def test_set_home_and_settings_return_true(robot):
    robot.ptp(mode=1, x=250, y=0, z=0, r=0)
    assert robot.set_home() is True
    assert position(robot) == (200, 0, 50)
    assert robot.set_do("DO_01", 1) is True


# -- alarms stop the program --------------------------------------------------------


def test_unreachable_target_raises_at_the_ptp_call(robot):
    with pytest.raises(DobotKinematicError) as raised:
        robot.ptp(mode=1, **UNREACHABLE)
    assert raised.value.alarms == ["PLAN_INVERSE_CALCULATION"]  # target out of the workspace
    assert "clear_alarm()" in str(raised.value)


def test_arm_refuses_every_command_until_the_alarm_is_cleared(robot):
    with pytest.raises(DobotKinematicError):
        robot.ptp(mode=1, **UNREACHABLE)
    with pytest.raises(DobotKinematicError):
        robot.set_endeffector_suctioncup(enable=True, on=True)

    assert robot.clear_alarm() is True
    assert robot.ptp(mode=1, x=230, y=0, z=30, r=0) is True


def test_set_home_homes_during_an_alarm_and_clears_it(robot):
    robot.ptp(mode=1, x=250, y=40, z=0, r=0)
    with pytest.raises(DobotKinematicError):
        robot.ptp(mode=1, **UNREACHABLE)
    assert robot.set_home() is True  # as in DobotLab: no alarm error, the arm homes
    assert position(robot) == (200, 0, 50)
    assert not robot.get_alarms()


def test_set_home_raises_for_an_alarm_that_comes_back_after_homing(robot, monkeypatch):
    lasting = decode_alarms(encode_alarms([Alarm.PUBLIC_ANGLE_SENSOR_READ]))
    monkeypatch.setattr(robot, "get_alarms", lambda: lasting)
    with pytest.raises(DobotSystemAlarmError):
        robot.set_home()
    assert position(robot) == (200, 0, 50)  # homing itself ran


def test_commands_queued_before_an_alarm_do_not_resume_after_clearing(robot):
    with pytest.raises(DobotKinematicError):
        with robot.batch():
            robot.ptp(mode=1, **UNREACHABLE)
            robot.ptp(mode=1, x=260, y=0, z=0, r=0)
    robot.clear_alarm()
    time.sleep(0.3)
    assert position(robot) == (200, 0, 50)


def test_clear_alarm_raises_and_keeps_an_alarm_whose_cause_remains():
    arm = Magician(auto_start_queue=False)
    arm._transport = Mock(is_open=True)
    limit = encode_alarms([Alarm.LIMIT_POS_J2])

    def send_frame(command_id, control, params):
        if command_id == CommandID.GET_ALARMS_STATE:
            return unpack(pack(command_id, 0, limit))
        return unpack(pack(command_id, control))

    arm._transport.send_frame.side_effect = send_frame
    with pytest.raises(DobotKinematicError, match="still active after clear_alarm"):
        arm.clear_alarm()


@pytest.mark.parametrize(
    ("alarm", "error_class"),
    [
        (Alarm.PLAN_INVERSE_SINGULARITY, DobotKinematicError),
        (Alarm.MOVE_INVERSE_LIMIT, DobotKinematicError),
        (Alarm.LIMIT_NEG_J4, DobotKinematicError),
        (Alarm.LIMIT_POS_PARALLELOGRAM, DobotKinematicError),
        (Alarm.OVERSPEED_J3, DobotOverspeedError),
        (Alarm.LOST_STEP_J1, DobotLostStepError),
        (Alarm.PUBLIC_ANGLE_SENSOR_READ, DobotSystemAlarmError),
        (0x70, DobotAlarmError),  # not in the ALARM Description
    ],
)
def test_each_alarm_group_has_its_exception(alarm, error_class):
    active = decode_alarms(encode_alarms([alarm]))
    error = alarm_error(active, "heading", "remedy")
    assert type(error) is error_class
    assert isinstance(error, DobotAlarmError)
    assert error.alarms == active.names()


# -- batch ----------------------------------------------------------------------------


def test_batch_queues_inside_the_block_and_waits_at_its_end(robot):
    with robot.batch():
        robot.ptp(mode=2, x=230, y=20, z=10, r=0)
        robot.ptp(mode=2, x=230, y=-20, z=10, r=0)
        assert position(robot) == (200, 0, 50)  # nothing runs inside the block
    assert position(robot) == (230, -20, 10)


def test_batch_discards_its_commands_when_the_block_raises(robot):
    with pytest.raises(RuntimeError):
        with robot.batch():
            robot.ptp(mode=2, x=230, y=20, z=10, r=0)
            raise RuntimeError("error in the program")
    time.sleep(0.3)
    assert position(robot) == (200, 0, 50)


# -- the simulator queue and the shared arm -------------------------------------------


def test_simulator_runs_a_later_command_only_after_the_move_before_it():
    arm = FakeDobot("/dev/sim-order", speed_mm_per_s=100.0)
    try:
        move = struct.pack("<B4f", 1, 260.0, 0.0, 50.0, 0.0)
        arm.handle_frame(pack(CommandID.SET_PTP_CMD, 3, move))
        suction = unpack(
            arm.handle_frame(pack(CommandID.GET_SET_END_EFFECTOR_SUCTION_CUP, 3, b"\x01\x01"))
        )
        (suction_index,) = struct.unpack("<Q", suction.params[:8])
        current = unpack(arm.handle_frame(pack(CommandID.GET_QUEUED_CMD_CURRENT_INDEX, 0)))
        assert struct.unpack("<Q", current.params[:8])[0] < suction_index
    finally:
        arm.stop()


def test_a_finished_program_leaves_the_queue_running_for_the_next_one(robot):
    robot.ptp(mode=1, x=240, y=0, z=40, r=0)
    robot.disconnect()
    panel_side = Magician("/dev/sim0", via_broker=False, verbose=False, auto_start_queue=False)
    panel_side.connect()
    try:
        assert panel_side.set_home() is True
    finally:
        panel_side.disconnect()
