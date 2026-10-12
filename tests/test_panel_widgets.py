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


DIAGONAL = {
    "top":      ("X+", 1),
    "bottom":   ("X-", 2),
    "left":     ("Y-", 3),
    "right":    ("Y+", 4),
}
QUADRANT = {
    "top_left":     ("J1-", 1),
    "top_right":    ("J1+", 2),
    "bottom_left":  ("J2-", 3),
    "bottom_right": ("J2+", 4),
}


def press_and_release(pad, x_fraction, y_fraction):
    """Click at a point given as a fraction of the pad's disc radius from its centre."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    centre, radius = pad.disc()
    point = QPoint(round(centre.x() + x_fraction * radius), round(centre.y() + y_fraction * radius))
    QTest.mousePress(pad, Qt.LeftButton, Qt.NoModifier, point)
    QTest.mouseRelease(pad, Qt.LeftButton, Qt.NoModifier, point)


@pytest.mark.parametrize(
    ("x_fraction", "y_fraction", "expected"),
    [(0, -0.7, 1), (0, 0.7, 2), (-0.7, 0, 3), (0.7, 0, 4), (0.5, -0.2, 4), (-0.2, -0.5, 1)],
)
def test_diagonal_pad_segments_emit_their_command(application, x_fraction, y_fraction, expected):
    from pydobotlab.panel.widgets import JogPad

    pad = JogPad("X / Y", DIAGONAL)
    pad.resize(200, 200)
    commands, stops = [], []
    pad.jog.connect(commands.append)
    pad.stop.connect(lambda: stops.append(True))
    press_and_release(pad, x_fraction, y_fraction)
    assert commands == [expected]
    assert stops == [True]
    pad.close()


@pytest.mark.parametrize(
    ("x_fraction", "y_fraction", "expected"),
    [(-0.6, -0.6, 1), (0.6, -0.6, 2), (-0.6, 0.6, 3), (0.6, 0.6, 4)],
)
def test_quadrant_pad_segments_emit_their_command(application, x_fraction, y_fraction, expected):
    from pydobotlab.panel.widgets import JogPad

    pad = JogPad("J1 / J2", QUADRANT)
    pad.resize(200, 200)
    commands = []
    pad.jog.connect(commands.append)
    press_and_release(pad, x_fraction, y_fraction)
    assert commands == [expected]
    pad.close()


def test_pad_ignores_centre_hub_and_outside_disc(application):
    from pydobotlab.panel.widgets import JogPad

    pad = JogPad("X / Y", DIAGONAL)
    pad.resize(200, 200)
    commands, stops = [], []
    pad.jog.connect(commands.append)
    pad.stop.connect(lambda: stops.append(True))
    press_and_release(pad, 0.05, 0.05)  # centre hub
    press_and_release(pad, 0.95, 0.95)  # corner, outside the disc
    assert commands == [] and stops == []
    pad.close()


def test_disabling_pad_mid_press_stops_the_jog(application):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from pydobotlab.panel.widgets import JogPad

    pad = JogPad("X / Y", DIAGONAL)
    pad.resize(200, 200)
    stops = []
    pad.stop.connect(lambda: stops.append(True))
    centre, radius = pad.disc()
    QTest.mousePress(
        pad,
        Qt.LeftButton,
        Qt.NoModifier,
        QPoint(round(centre.x()), round(centre.y() - 0.7 * radius)),
    )
    pad.setEnabled(False)  # e.g. an alarm locks jogging while the button is held
    assert stops == [True]
    pad.close()


def test_pad_rejects_unknown_segment_names(application):
    from pydobotlab.panel.widgets import JogPad

    with pytest.raises(ValueError, match="segments must be"):
        JogPad("bad", {"up": ("X+", 1), "down": ("X-", 2), "left": ("Y-", 3), "right": ("Y+", 4)})


def test_pad_paints_in_every_state(application):
    from pydobotlab.panel.widgets import JogPad

    for segments in (DIAGONAL, QUADRANT):
        pad = JogPad("pad", segments)
        pad.resize(180, 180)
        pad.grab()
        pad.setEnabled(False)
        pad.grab()
        pad.close()


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
        from pydobotlab import CommandID

        sent_frames = []
        monkeypatch.setattr(
            panel._bot,
            "write_command",
            lambda command_id, params: sent_frames.append((command_id, params)),
        )
        panel.set_laser(True, False)
        # Sent immediately, so the button acts at once even while a script moves.
        assert sent_frames == [(CommandID.GET_SET_END_EFFECTOR_LASER, b"\x01\x00")]
    finally:
        if panel is not None:
            panel.close()
        simulator.stop_all()


def test_panel_adopts_the_arm_speed_and_follows_script_changes(application, monkeypatch):
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
    with Dobot("/dev/sim0", via_broker=False, verbose=False) as script:
        script.motion_params = (30, 30)
    panel = None
    try:
        panel = panel_module.ControlPanel("/dev/sim0")
        assert panel._speed_slider.value() == 30
        assert panel._bot.get_arm_speed_ratio(1) == 30  # opening the panel kept the speed
        assert panel._bot.get_arm_speed_ratio(0) == 30  # and jogging uses it

        panel._bot.motion_params = (70, 70)  # a script changes the speed
        panel.sync_speed(panel._bot.get_arm_speed_ratio(1))  # what the 1 Hz poll does
        assert panel._speed_slider.value() == 70
        assert panel._bot.get_arm_speed_ratio(0) == 70
    finally:
        if panel is not None:
            panel.close()
        simulator.stop_all()


NO_MAGICIAN_NOTE = (
    "No Dobot Magician devices were found.\nCheck the USB cable and power, then click Refresh."
)


def listed_rows(hub) -> list[str]:
    """Texts of the hub's top-level rows."""
    tree = hub._device_list
    return [tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())]


def test_hub_lists_ports_only_and_explains_permission_once(application, monkeypatch):
    from pydobotlab import DiscoveredDobot, Discovery, ProbeFailure
    from pydobotlab.panel.hub import HubWindow

    monkeypatch.setattr(Discovery, "discover_with_diagnostics", staticmethod(lambda: ([], [])))
    hub = HubWindow()
    try:
        hub._worker.wait()
        hub.show_discovery_results([DiscoveredDobot(port="COM3", serial_number="DT1234567890")])
        assert listed_rows(hub) == ["COM3", "Other devices (0)"]

        hub.show_discovery_results(
            [],
            [
                ProbeFailure("/dev/ttyACM0", "", "permission", "Permission denied for X: join"),
                ProbeFailure("/dev/ttyS0", "", "permission", "Permission denied for Y: join"),
                ProbeFailure("/dev/ttyUSB0", "", "busy", "locked"),
            ],
        )
        lines = listed_rows(hub)
        assert lines[0] == NO_MAGICIAN_NOTE
        assert sum("Permission denied" in line for line in lines) == 1
        assert "/dev/ttyUSB0    port is busy" in lines
        assert not any("brltty" in line or "try " in line for line in lines)
    finally:
        hub.close()


@pytest.mark.parametrize("magician_found", [False, True])
def test_hub_groups_other_devices_in_a_collapsed_list(application, monkeypatch, magician_found):
    from pydobotlab import DiscoveredDobot, Discovery, ProbeFailure
    from pydobotlab.panel.hub import HubWindow

    monkeypatch.setattr(Discovery, "discover_with_diagnostics", staticmethod(lambda: ([], [])))
    hub = HubWindow()
    try:
        hub._worker.wait()
        devices = [DiscoveredDobot(port="/dev/ttyACM0", serial_number="DT1")] * magician_found
        hub.show_discovery_results(
            devices,
            [
                ProbeFailure("COM4", "Arduino Uno (COM4)", "no_reply", "'COM4' is not a Dobot"),
                ProbeFailure("COM5", "", "no_reply", "'COM5' is not a Dobot Magician"),
            ],
        )
        first_row = "/dev/ttyACM0" if magician_found else NO_MAGICIAN_NOTE
        assert listed_rows(hub) == [first_row, "Other devices (2)"]
        group = hub._device_list.topLevelItem(1)
        assert [group.child(i).text(0) for i in range(group.childCount())] == [
            "COM4    Arduino Uno",
            "COM5",
        ]
        assert not group.isExpanded()
        hub.toggle_group(group)  # what a click on the row does
        assert group.isExpanded()

        hub._device_list.setCurrentItem(group)
        assert hub.selected_port() is None  # other devices cannot be opened
    finally:
        hub.close()


def test_hub_and_panel_show_the_version(application, monkeypatch):
    import serial
    import serial.tools.list_ports

    import pydobotlab.panel.panel as panel_module
    import pydobotlab.simulator as simulator
    from pydobotlab import Discovery, Dobot, __version__
    from pydobotlab.panel.hub import HubWindow

    monkeypatch.setattr(Discovery, "discover_with_diagnostics", staticmethod(lambda: ([], [])))
    monkeypatch.setattr(serial, "Serial", serial.Serial)
    monkeypatch.setattr(serial.tools.list_ports, "comports", serial.tools.list_ports.comports)
    monkeypatch.setattr(simulator, "_INSTALLED", False)
    simulator.install_simulator(arms=1)
    monkeypatch.setattr(panel_module, "Dobot", lambda port: Dobot(port, via_broker=False))
    hub = HubWindow()
    panel = None
    try:
        hub._worker.wait()
        panel = panel_module.ControlPanel("/dev/sim0")
        for window in (hub, panel):
            assert window._version_label.text() == f"pydobotlab v{__version__}"
            window.statusBar().showMessage("a status message")
            assert window._version_label.isVisibleTo(window)  # stays while messages show
    finally:
        if panel is not None:
            panel.close()
        hub.close()
        simulator.stop_all()


def test_hub_runs_one_scan_at_a_time(application, monkeypatch):
    import threading
    import time

    from pydobotlab import Discovery
    from pydobotlab.panel.hub import HubWindow

    scans = []
    scan_may_finish = threading.Event()

    def scan():
        scans.append(time.monotonic())
        scan_may_finish.wait(5)
        return [], []

    monkeypatch.setattr(Discovery, "discover_with_diagnostics", staticmethod(scan))
    hub = HubWindow()
    try:
        first_scan = hub._worker
        hub.refresh()  # as when a panel closes during the startup scan
        assert hub._worker is first_scan

        scan_may_finish.set()
        deadline = time.monotonic() + 5
        while (hub._worker is not None or len(scans) < 2) and time.monotonic() < deadline:
            application.processEvents()
            time.sleep(0.01)

        assert len(scans) == 2  # the requested scan ran after the first one
        assert listed_rows(hub) == [NO_MAGICIAN_NOTE, "Other devices (0)"]
    finally:
        scan_may_finish.set()
        hub.close()


def test_watchdog_disconnects_only_after_consecutive_failures(application, monkeypatch):
    import serial
    import serial.tools.list_ports

    import pydobotlab.panel.panel as panel_module
    import pydobotlab.simulator as simulator
    from pydobotlab import Dobot, DobotTimeoutError

    monkeypatch.setattr(serial, "Serial", serial.Serial)
    monkeypatch.setattr(serial.tools.list_ports, "comports", serial.tools.list_ports.comports)
    monkeypatch.setattr(simulator, "_INSTALLED", False)
    simulator.install_simulator(arms=1)
    monkeypatch.setattr(panel_module, "Dobot", lambda port: Dobot(port, via_broker=False))
    panel = None
    try:
        panel = panel_module.ControlPanel("/dev/sim0")
        assert panel._connected
        healthy_check = panel._bot.get_device_version

        def lost_reply():
            raise DobotTimeoutError("no answer")

        monkeypatch.setattr(panel._bot, "get_device_version", lost_reply)
        panel.check_connection()
        panel.check_connection()
        assert panel._connected  # two lost replies in a row are tolerated

        monkeypatch.setattr(panel._bot, "get_device_version", healthy_check)
        panel.check_connection()  # recovery resets the count
        monkeypatch.setattr(panel._bot, "get_device_version", lost_reply)
        panel.check_connection()
        panel.check_connection()
        assert panel._connected  # still only 2 since the last success

        panel.check_connection()  # third in a row
        assert not panel._connected
        assert panel._reconnect_button.isVisibleTo(panel)
    finally:
        if panel is not None:
            panel.close()
        simulator.stop_all()
