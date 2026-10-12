"""Failures on the connection path must surface, not vanish."""

from __future__ import annotations

import threading

import pytest

from pydobotlab import Dobot, DobotConnectionError, DobotTimeoutError


def make_robot() -> Dobot:
    return Dobot("/dev/test-visibility", via_broker=False, verbose=True)


def test_jog_stop_raises_when_the_retry_also_fails(monkeypatch):
    robot = make_robot()
    attempts = []

    def failing_jog(command, mode=None):
        attempts.append(command)
        raise DobotTimeoutError("no answer")

    monkeypatch.setattr(robot, "jog", failing_jog)
    with pytest.raises(DobotTimeoutError):
        robot.jog_stop()
    assert len(attempts) == 2  # one try plus one retry


def test_jog_stop_succeeds_on_retry(monkeypatch):
    robot = make_robot()
    attempts = []

    def flaky_jog(command, mode=None):
        attempts.append(command)
        if len(attempts) == 1:
            raise DobotConnectionError("blip")

    monkeypatch.setattr(robot, "jog", flaky_jog)
    robot.jog_stop()
    assert len(attempts) == 2


def run_stream_until(robot, outcomes, **stream_options):
    """Drive the pose stream through ``outcomes`` (exception or pose), then stop it."""
    from pydobotlab import Pose

    done = threading.Event()
    remaining = list(outcomes)

    def get_pose():
        if not remaining:
            done.set()
            return Pose(*range(8))
        outcome = remaining.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return Pose(*range(8))

    robot.get_pose = get_pose
    robot.start_pose_stream(hz=500, **stream_options)
    assert done.wait(5)
    robot.stop_pose_stream()


def test_pose_stream_reports_a_failure_streak_once_then_recovery(capsys):
    robot = make_robot()
    problem = DobotTimeoutError("arm silent")
    run_stream_until(robot, [problem, problem, problem, None, None])
    captured = capsys.readouterr()
    assert captured.err.count("Pose stream failing: arm silent") == 1
    assert "Pose stream recovered." in captured.out


def test_pose_stream_on_error_callback_replaces_the_default_report(capsys):
    robot = make_robot()
    seen = []
    run_stream_until(
        robot,
        [DobotTimeoutError("first"), DobotTimeoutError("again"), None],
        on_error=seen.append,
    )
    assert [str(error) for error in seen] == ["first"]
    captured = capsys.readouterr()
    assert captured.err == "" and captured.out == ""
