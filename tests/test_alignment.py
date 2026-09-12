"""Tests asserting alignment with the DobotLab 3.6.x official surface.

Hardware-free: we only check method existence, signatures, and pure-Python
helpers (Pose iteration, IO-string parsing, property descriptors).
"""

from __future__ import annotations

import inspect

import pytest

from pydobotlab import Dobot, Pose
from pydobotlab.device import parse_io_port

# ---- 1. Every documented official method is present ---------------------

OFFICIAL_METHODS = [
    # (3.6.1 - 3.6.28) - name only; signatures are checked separately.
    "ptp",  # 3.6.1
    "set_device_withl",  # 3.6.2
    "set_ptpl_params",  # 3.6.3
    "set_ptpwithl_cmd",  # 3.6.4
    "set_r",  # 3.6.5
    # 3.6.6 motion_params is a property (checked below)
    # 3.6.7 jump_params is a property (checked below)
    "set_multiplexing",  # 3.6.8
    "set_pwm",  # 3.6.9
    "set_do",  # 3.6.10
    "get_di",  # 3.6.11
    "get_adc",  # 3.6.12
    "set_endeffector_suctioncup",  # 3.6.13
    "set_endeffector_gripper",  # 3.6.14
    "set_infrared_sensor",  # 3.6.15
    "get_infrared_sensor",  # 3.6.16
    "set_color_sensor",  # 3.6.17
    "get_color_sensor",  # 3.6.18
    "wait",  # 3.6.19
    "set_home",  # 3.6.20
    "get_pose",  # 3.6.21
    "get_posel",  # 3.6.22
    "clear_alarm",  # 3.6.23
    "get_arm_speed_ratio",  # 3.6.24
    "set_lost_step_params",  # 3.6.25
    "set_lost_step_cmd",  # 3.6.26
    "get_lost_step_result",  # 3.6.27
    "set_converyor",  # 3.6.28 - official typo preserved
]


@pytest.mark.parametrize("name", OFFICIAL_METHODS)
def test_official_method_exists(name):
    assert callable(getattr(Dobot, name)), f"Dobot.{name} should be callable"


def test_motion_params_is_a_property():
    assert isinstance(Dobot.__dict__["motion_params"], property)


def test_jump_params_is_a_property():
    assert isinstance(Dobot.__dict__["jump_params"], property)


def test_set_conveyor_alias_for_typo_function():
    """We expose both the official typo and a sane spelling."""
    assert Dobot.set_conveyor is Dobot.set_converyor


# ---- 2. Signatures match the GitBook ---------------------------------


@pytest.mark.parametrize(
    "method, params",
    [
        ("ptp", ["self", "mode", "x", "y", "z", "r"]),
        ("set_device_withl", ["self", "enable", "version"]),
        ("set_ptpl_params", ["self", "vel", "accel"]),
        ("set_ptpwithl_cmd", ["self", "mode", "x", "y", "z", "r", "l"]),
        ("set_r", ["self", "r"]),
        ("set_multiplexing", ["self", "io", "multiplex"]),
        ("set_pwm", ["self", "io", "freq", "cycle"]),
        ("set_do", ["self", "io", "level"]),
        ("get_di", ["self", "io"]),
        ("get_adc", ["self", "io"]),
        ("set_endeffector_suctioncup", ["self", "enable", "on"]),
        ("set_endeffector_gripper", ["self", "enable", "on"]),
        ("set_infrared_sensor", ["self", "port", "enable", "version"]),
        ("get_infrared_sensor", ["self", "port"]),
        ("set_color_sensor", ["self", "port", "enable", "version"]),
        ("wait", ["self", "second"]),
        ("set_home", ["self"]),
        ("get_pose", ["self"]),
        ("get_posel", ["self"]),
        ("clear_alarm", ["self"]),
        ("get_color_sensor", ["self"]),
        ("set_lost_step_cmd", ["self"]),
        ("get_lost_step_result", ["self"]),
        ("get_arm_speed_ratio", ["self", "mode"]),
        ("set_lost_step_params", ["self", "value"]),
        ("set_converyor", ["self", "index", "enable", "speed"]),
    ],
)
def test_signature_matches_gitbook(method, params):
    sig = inspect.signature(getattr(Dobot, method))
    actual = list(sig.parameters.keys())
    assert actual[: len(params)] == params, (
        f"Dobot.{method} signature drift - expected {params}, got {actual}"
    )
    for parameter in list(sig.parameters.values())[len(params) :]:
        assert parameter.kind == inspect.Parameter.KEYWORD_ONLY
        assert parameter.default is not inspect.Parameter.empty
    arguments = {name: 0 for name in params if name != "self"}
    sig.bind(None, **arguments)


def test_get_color_sensor_takes_no_args():
    sig = inspect.signature(Dobot.get_color_sensor)
    assert list(sig.parameters.keys()) == ["self"]


# ---- 3. Pose iteration matches the GitBook tuple shape ------------------


def test_pose_iterates_as_xyzr_then_jointangle_list():
    p = Pose(x=1.0, y=2.0, z=3.0, r=4.0, j1=10.0, j2=20.0, j3=30.0, j4=40.0)
    x, y, z, r, joints = p
    assert (x, y, z, r) == (1.0, 2.0, 3.0, 4.0)
    assert joints == [10.0, 20.0, 30.0, 40.0]


def test_print_pose_includes_rotation_and_all_joints_without_changing_values(capsys):
    pose = Pose(1.23456, -2.34567, 3.45678, -4.56789, 10.1, -20.2, 30.3, -40.4)

    print(pose)

    assert capsys.readouterr().out == (
        "Pose(x=1.23, y=-2.35, z=3.46, r=-4.57, joints=[10.10, -20.20, 30.30, -40.40])\n"
    )
    assert pose.as_xyzr() == (1.23456, -2.34567, 3.45678, -4.56789)
    assert pose.joints == [10.1, -20.2, 30.3, -40.4]


def test_pose_attribute_access_still_works():
    p = Pose(1, 2, 3, 4, 5, 6, 7, 8)
    assert (p.x, p.y, p.z, p.r) == (1, 2, 3, 4)
    assert (p.j1, p.j2, p.j3, p.j4) == (5, 6, 7, 8)
    assert p.joints == [5, 6, 7, 8]


# ---- 4. Stepper class attributes ----------------------------------------


def test_stepper_class_attributes():
    assert Dobot.Stepper1 == 0
    assert Dobot.Stepper2 == 1


# ---- 5. IO-string parser -------------------------------------------------


@pytest.mark.parametrize(
    "io, expected",
    [
        ("DO_01", 1),
        ("DO_20", 20),
        ("DI_15", 15),
        ("do_03", 3),  # case insensitive
        ("DO01", 1),  # also accepts no underscore
        (1, 1),
        (20, 20),
        ("7", 7),  # bare numeric string
    ],
)
def test_io_to_port_accepts_pydobotlab_strings_and_ints(io, expected):
    assert parse_io_port(io) == expected


@pytest.mark.parametrize(
    "bad",
    [
        "DO_00",  # range
        "DO_21",
        "ZZ_01",
        0,
        21,
        -1,
        "garbage",
        None,
    ],
)
def test_io_to_port_rejects_garbage(bad):
    with pytest.raises((ValueError, TypeError)):
        parse_io_port(bad)


# ---- 6. Backwards-compat aliases still work ----------------------------


def test_old_aliases_present():
    """Code that used the prior names should keep working."""
    for old_name, _new_name in [
        ("home", "set_home"),
        ("clear_alarms", "clear_alarm"),
        ("wait_seconds", "wait"),
        ("get_pose_l", "get_posel"),
        ("get_slideway_pose", "get_posel"),
    ]:
        assert callable(getattr(Dobot, old_name)), f"alias {old_name} missing"
