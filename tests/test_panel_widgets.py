"""Exercise Qt signal wiring against simulated hardware without a display."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")


@pytest.fixture
def application(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance() or QApplication([])
    yield application
    application.processEvents()


def test_jog_button_press_and_release_signals(application):
    from pydobotlab.panel.widgets import JogButton
    from pydobotlab.protocol import JOGCmd

    button = JogButton("X+", JOGCmd.AP_DOWN)
    commands = []
    releases = []
    button.pressedCmd.connect(commands.append)
    button.releasedCmd.connect(lambda: releases.append(True))
    button.click()
    assert commands == [int(JOGCmd.AP_DOWN)]
    assert releases == [True]
    button.close()


def test_jump_parameter_update_does_not_echo(application):
    from pydobotlab.panel.widgets import JumpParamsCard

    card = JumpParamsCard()
    changes = []
    card.valuesChanged.connect(lambda zlimit, height: changes.append((zlimit, height)))
    card.update_values(90, 30)
    assert changes == []
    card.emit_values_changed()
    assert changes == [(90.0, 30.0)]
    card.close()


def test_panel_connects_and_updates_simulated_arm(application, monkeypatch):
    import serial
    import serial.tools.list_ports

    import pydobotlab.panel.panel as panel_module
    import pydobotlab.simulator as simulator
    from pydobotlab import Dobot

    monkeypatch.setattr(serial, "Serial", serial.Serial)
    monkeypatch.setattr(serial.tools.list_ports, "comports", serial.tools.list_ports.comports)
    monkeypatch.setattr(simulator, "_INSTALLED", False)
    simulator.install_simulator(arms=1)
    monkeypatch.setattr(panel_module, "Dobot", lambda port: Dobot(port, via_broker=False))
    panel = None
    try:
        panel = panel_module.ControlPanel("/dev/sim0")
        assert panel._bot.is_open
        panel.sync_speed(35)
        panel.apply_speed()
        assert panel._bot.get_arm_speed_ratio(1) == 35
        assert panel._bot.get_arm_speed_ratio(0) == 35
        panel.apply_jump_params(90, 30)
        assert panel._bot.jump_params == (90, 30)
        laser_calls = []
        monkeypatch.setattr(
            panel._bot,
            "set_endeffector_laser",
            lambda **values: laser_calls.append(values),
        )
        panel.set_laser(True, False)
        assert laser_calls == [{"enable": True, "on": False}]
    finally:
        if panel is not None:
            panel.close()
        simulator.stop_all()
