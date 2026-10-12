"""Packet regressions checked against Dobot V1.1.5 and DobotLink.

Vendor source: https://github.com/Dobot-Arm/DobotLink/blob/main/Plugins/
MagicDevicePlugin/Protocol2/DMagicianProtocol.cpp
These tests use a mock transport and never connect to hardware.
"""

from __future__ import annotations

import struct
from unittest.mock import Mock, call

import pytest

from pydobotlab import CommandID, Magician, PTPMode
from pydobotlab.protocol import pack, unpack


@pytest.fixture
def robot():
    arm = Magician(auto_start_queue=False)
    arm._transport = Mock(is_open=True)
    return arm


def reply_to_queued_command(robot, command_id: int) -> None:
    """Queue the command as index 42, then report it executed with no alarms."""

    def send_frame(sent_command_id, control, params):
        if sent_command_id == CommandID.GET_QUEUED_CMD_CURRENT_INDEX:
            return unpack(pack(sent_command_id, 0, struct.pack("<Q", 42)))
        if sent_command_id == CommandID.GET_ALARMS_STATE:
            return unpack(pack(sent_command_id, 0, bytes(16)))
        return unpack(pack(command_id, 3, struct.pack("<Q", 42)))

    robot._transport.send_frame.side_effect = send_frame


def first_frame_sent(robot):
    return robot._transport.send_frame.call_args_list[0]


@pytest.mark.parametrize("method", ["set_color_sensor", "set_infrared_sensor"])
@pytest.mark.parametrize("enable", [True, False])
def test_sensor_setup_encodes_enable_before_port(robot, method, enable):
    command_id = 137 if method == "set_color_sensor" else 138
    reply_to_queued_command(robot, command_id)

    assert getattr(robot, method)(port=4, enable=enable, version=1) is True

    assert first_frame_sent(robot) == call(command_id, 3, bytes([enable, 4, 1]))


def test_color_read_sends_no_port_and_returns_rgb(robot):
    robot._transport.send_frame.return_value = unpack(pack(137, 0, bytes([255, 12, 34])))

    assert robot.get_color_sensor() == (255, 12, 34)

    robot._transport.send_frame.assert_called_once_with(137, 0, b"")


def test_infrared_read_preserves_port_and_returns_state(robot):
    # DobotLink includes the port byte even though the PDF's read table omits it.
    robot._transport.send_frame.return_value = unpack(pack(138, 0, b"\x01"))

    assert robot.get_infrared_sensor(port=4) == 1

    robot._transport.send_frame.assert_called_once_with(138, 0, b"\x04")


@pytest.mark.parametrize(
    "method, arguments, command_id, payload",
    [
        ("set_device_withl", {"enable": True, "version": 1}, 3, b"\x01\x01"),
        ("set_lost_step_params", {"value": 10}, 170, struct.pack("<f", 10)),
    ],
)
def test_immediate_settings_accept_empty_acknowledgements(
    robot, method, arguments, command_id, payload
):
    # These commands cannot return an eight-byte queued-command index.
    robot._transport.send_frame.return_value = unpack(pack(command_id, 1))

    assert getattr(robot, method)(**arguments) is True

    robot._transport.send_frame.assert_called_once_with(command_id, 1, payload)
    assert robot._last_queued_index == 0


@pytest.mark.parametrize("mode", range(10))
def test_all_official_ptp_modes_have_names_and_preserve_coordinates(robot, mode):
    reply_to_queued_command(robot, 84)

    assert robot.ptp(mode=PTPMode(mode), x=200, y=-20, z=50, r=30) is True

    assert first_frame_sent(robot) == call(
        84, 3, bytes([mode]) + struct.pack("<4f", 200, -20, 50, 30)
    )


def test_slideway_motion_preserves_the_official_l_argument(robot):
    reply_to_queued_command(robot, 86)

    assert robot.set_ptpwithl_cmd(mode=1, x=200, y=0, z=50, r=30, l=100) is True

    assert first_frame_sent(robot) == call(86, 3, b"\x01" + struct.pack("<5f", 200, 0, 50, 30, 100))


def test_jump_property_preserves_official_order_and_converts_wire_order(robot):
    reply_to_queued_command(robot, 82)

    robot.jump_params = 100, 20

    assert first_frame_sent(robot) == call(82, 3, struct.pack("<2f", 20, 100))
    robot._transport.send_frame.side_effect = None
    robot._transport.send_frame.return_value = unpack(pack(82, 0, struct.pack("<2f", 20, 100)))
    assert robot.jump_params == (100, 20)


def test_conveyor_uses_signed_pulse_rate_from_dobotlink(robot):
    # DobotLink uses a signed integer for speed, despite the PDF saying float.
    reply_to_queued_command(robot, 135)

    assert robot.set_converyor(index=robot.Stepper2, enable=True, speed=-250) is True

    assert first_frame_sent(robot) == call(135, 3, b"\x01\x01" + struct.pack("<i", -250))
