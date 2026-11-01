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


# fmt: off
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
# fmt: on


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


def test_harmless_qt_warnings_are_hidden(application):
    from PySide6.QtCore import QLoggingCategory

    from pydobotlab.panel.app import hide_harmless_qt_warnings

    hide_harmless_qt_warnings()
    for name in ("qt.qpa.wayland.textinput", "qt.qpa.services"):
        assert not QLoggingCategory(name).isWarningEnabled()
    assert QLoggingCategory("qt.qpa.wayland").isWarningEnabled()  # other warnings still show


def test_panel_windows_show_the_pydobotlab_icon(application):
    from pydobotlab.panel.app import show_panel_icon

    show_panel_icon(application)
    assert not application.windowIcon().isNull()
    assert application.desktopFileName() == "pydobotlab-panel"  # the shortcut's .desktop file


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
    monkeypatch.setattr(
        panel_module, "Dobot", lambda port, **options: Dobot(port, **options, via_broker=False)
    )
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


def test_panel_sets_the_saved_speed_and_follows_script_changes(application, monkeypatch):
    import serial
    import serial.tools.list_ports

    import pydobotlab.panel.panel as panel_module
    import pydobotlab.simulator as simulator
    from pydobotlab import CommandID, Dobot
    from pydobotlab.config import saved_arm_speed
    from pydobotlab.protocol import pack_floats

    monkeypatch.setattr(serial, "Serial", serial.Serial)
    monkeypatch.setattr(serial.tools.list_ports, "comports", serial.tools.list_ports.comports)
    monkeypatch.setattr(simulator, "_INSTALLED", False)
    simulator.install_simulator(arms=1)
    monkeypatch.setattr(
        panel_module, "Dobot", lambda port, **options: Dobot(port, **options, via_broker=False)
    )
    with Dobot("/dev/sim0", via_broker=False, verbose=False) as script:
        script.motion_params = (30, 30)  # saved for this arm
        # Changed without saving, as another program would.
        script.write_command(CommandID.GET_SET_PTP_COMMON_PARAMS, pack_floats(80, 80))
    panel = None
    try:
        panel = panel_module.ControlPanel("/dev/sim0")
        assert panel._speed_slider.value() == 30
        assert panel._bot.get_arm_speed_ratio(1) == 30  # opening the panel set the saved speed
        assert panel._bot.get_arm_speed_ratio(0) == 30  # and jogging uses it

        panel._bot.motion_params = (70, 70)  # a script changes the speed
        panel.sync_speed(panel._bot.get_arm_speed_ratio(1))  # what the 1 Hz poll does
        assert panel._speed_slider.value() == 70
        assert panel._bot.get_arm_speed_ratio(0) == 70
        assert saved_arm_speed(panel._serial_number) == 70
    finally:
        if panel is not None:
            panel.close()
        simulator.stop_all()


def test_every_slider_change_is_saved_and_set_on_the_arm(application, simulated_arm):
    from pydobotlab.config import saved_arm_speed
    from pydobotlab.panel.panel import ControlPanel

    panel = ControlPanel("/dev/sim0")
    slider = panel._speed_slider
    try:
        slider.setValue(80)  # as a click on the track, the mouse wheel, or a key does
        assert panel._bot.get_arm_speed_ratio(1) == 80
        assert panel._bot.get_arm_speed_ratio(0) == 80
        assert saved_arm_speed(panel._serial_number) == 80

        slider.setSliderDown(True)  # a drag is set when the slider is released
        slider.setValue(20)
        assert panel._bot.get_arm_speed_ratio(1) == 80
        slider.setSliderDown(False)
        assert panel._bot.get_arm_speed_ratio(1) == 20
        assert saved_arm_speed(panel._serial_number) == 20
    finally:
        panel.close()


NO_MAGICIAN_NOTE = (
    "No Dobot Magician devices were found.\nCheck the USB cable and power, then click Refresh."
)


def listed_rows(hub) -> list[str]:
    """Texts of the hub's top-level rows; the separator line reads as "---"."""
    tree = hub._device_list
    rows = []
    for index in range(tree.topLevelItemCount()):
        item = tree.topLevelItem(index)
        widget = tree.itemWidget(item, 0)
        is_separator = widget is not None and widget.objectName() == "separator"
        rows.append("---" if is_separator else item.text(0))
    return rows


FAILED_PORTS = [
    ("/dev/ttyACM0", "permission", "Permission denied for X: join"),
    ("/dev/ttyS0", "permission", "Permission denied for Y: join"),
    ("/dev/ttyUSB0", "busy", "locked"),
    ("/dev/ttyS1", "no_reply", "'/dev/ttyS1' is not a Dobot Magician"),
]


def test_without_a_magician_the_hub_says_why_without_listing_the_ports(application, monkeypatch):
    from pydobotlab import Discovery, ProbeFailure
    from pydobotlab.panel.hub import HubWindow

    monkeypatch.setattr(Discovery, "discover_with_diagnostics", staticmethod(lambda: ([], [])))
    hub = HubWindow()
    try:
        hub._worker.wait()
        failures = [ProbeFailure(port, "", reason, detail) for port, reason, detail in FAILED_PORTS]
        hub.show_discovery_results([], failures)
        assert listed_rows(hub) == [
            NO_MAGICIAN_NOTE
            + "\nA serial port is busy. Close the script or program using it, then click Refresh."
        ]
        assert hub._notice.text() == "Permission denied for X: join"  # the cause, no port list
        assert hub.statusBar().currentMessage() == "no Dobot Magician devices found"
    finally:
        hub.close()


def test_developer_hub_lists_ports_only_and_explains_permission_once(application, monkeypatch):
    from pydobotlab import DiscoveredDobot, Discovery, ProbeFailure
    from pydobotlab.panel.hub import HubWindow

    monkeypatch.setattr(Discovery, "discover_with_diagnostics", staticmethod(lambda: ([], [])))
    hub = HubWindow(developer=True)
    try:
        hub._worker.wait()
        hub.show_discovery_results([DiscoveredDobot(port="COM3", serial_number="DT1234567890")])
        assert listed_rows(hub) == ["Dobot Magician 1    COM3", "---", "Other devices (0)"]

        failures = [ProbeFailure(port, "", reason, detail) for port, reason, detail in FAILED_PORTS]
        hub.show_discovery_results([], failures)
        lines = listed_rows(hub)
        assert lines[0] == NO_MAGICIAN_NOTE
        assert lines[-2:] == ["---", "Other devices (1)"]
        assert hub.statusBar().currentMessage().endswith("ports tried: 4 - hover for details")
        notice = hub._notice.text()
        assert notice.count("Permission denied") == 1  # explained once, above the list
        assert notice.endswith("Affected ports: /dev/ttyACM0, /dev/ttyS0")
        assert not any("Permission denied" in line for line in lines)
        assert (
            "/dev/ttyUSB0    port is busy: close the script or program using it, then Refresh"
            in lines
        )
        assert not any("brltty" in line or "try " in line for line in lines)
    finally:
        hub.close()


def test_hub_wraps_a_long_message_instead_of_cutting_it(application, monkeypatch):
    from pydobotlab import Discovery, ProbeFailure
    from pydobotlab.panel.hub import HubWindow

    monkeypatch.setattr(Discovery, "discover_with_diagnostics", staticmethod(lambda: ([], [])))
    hub = HubWindow()
    try:
        hub._worker.wait()
        application.processEvents()  # the startup scan's empty result
        message = (
            "Permission denied for /dev/ttyACM0. " + "Join the dialout group and log in again. " * 4
        )
        hub.show_discovery_results([], [ProbeFailure("/dev/ttyACM0", "", "permission", message)])
        hub.show()
        application.processEvents()
        notice = hub._notice
        assert notice.isVisible() and notice.text().startswith(message)
        assert notice.width() <= hub.width()  # within the window
        assert notice.height() >= 3 * notice.fontMetrics().height()  # wrapped over lines

        hub.show_discovery_results([], [])
        assert not notice.isVisible()  # gone once the problem is
    finally:
        hub.close()


@pytest.mark.parametrize("magician_found", [False, True])
def test_hub_groups_other_devices_in_a_collapsed_list(application, monkeypatch, magician_found):
    from pydobotlab import DiscoveredDobot, Discovery, ProbeFailure
    from pydobotlab.panel.hub import HubWindow

    monkeypatch.setattr(Discovery, "discover_with_diagnostics", staticmethod(lambda: ([], [])))
    # Without a Magician, only developer mode lists the other devices.
    hub = HubWindow(developer=not magician_found)
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
        first_row = "Dobot Magician 1" if magician_found else NO_MAGICIAN_NOTE
        assert listed_rows(hub) == [first_row, "---", "Other devices (2)"]
        group = hub._device_list.topLevelItem(2)
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
    monkeypatch.setattr(
        panel_module, "Dobot", lambda port, **options: Dobot(port, **options, via_broker=False)
    )
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


@pytest.mark.parametrize(("answer", "quits"), [("No", False), ("Yes", True)])
def test_hub_asks_before_quitting_while_scripts_are_connected(
    application, monkeypatch, answer, quits
):
    from types import SimpleNamespace

    import pydobotlab.panel.hub as hub_module
    from pydobotlab import Discovery

    monkeypatch.setattr(Discovery, "discover_with_diagnostics", staticmethod(lambda: ([], [])))
    questions = []

    def ask(parent, title, text, buttons, default):
        questions.append(text)
        return getattr(hub_module.QMessageBox, answer)

    monkeypatch.setattr(hub_module.QMessageBox, "question", ask)
    hub = hub_module.HubWindow(broker=SimpleNamespace(client_count=lambda: 1))
    try:
        hub._worker.wait()
        hub.show()
        assert hub.close() is quits
        assert hub.isVisible() is not quits
        assert questions == [
            "1 script is connected to an arm through the control panel.\n"
            "Quitting disconnects it from the arm.\n\nQuit anyway?"
        ]
    finally:
        hub._broker = None
        hub.close()


def test_a_panel_window_keeps_the_queued_moves_of_a_script(application, simulated_arm, monkeypatch):
    import time

    import pydobotlab.panel.panel as panel_module
    from pydobotlab import Discovery, Dobot
    from pydobotlab.broker import DobotBroker
    from pydobotlab.panel.hub import HubWindow

    monkeypatch.setattr(Discovery, "discover_with_diagnostics", staticmethod(lambda: ([], [])))
    with DobotBroker(port=0) as broker:
        through_broker = {"via_broker": True, "broker_port": broker.port, "verbose": False}
        monkeypatch.setattr(
            panel_module,
            "Dobot",
            lambda port, **options: Dobot(port, **{**options, **through_broker}),
        )
        hub = HubWindow(broker=broker)
        try:
            hub._worker.wait()
            with Dobot("/dev/sim0", **through_broker) as script:
                script.move_to(200, 0, 50)
                script.move_to(250, 50, 30, wait=False)
                last_move = script.move_to(200, -50, 30, wait=False)
                hub.open_panel("/dev/sim0")  # the window opens and closes during the moves
                assert hub.script_count() == 1  # the panel window is not counted
                hub._panels["/dev/sim0"].close()
                script.wait_for(last_move, timeout=15)
                pose = script.get_pose()
                assert (round(pose.x), round(pose.y), round(pose.z)) == (200, -50, 30)

            deadline = time.monotonic() + 5
            while hub.script_count() and time.monotonic() < deadline:
                time.sleep(0.01)
            assert hub.script_count() == 0
        finally:
            hub.close()


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
        assert listed_rows(hub) == [NO_MAGICIAN_NOTE]
    finally:
        scan_may_finish.set()
        hub.close()


NOT_RESPONDING = (
    "The arm is not responding. Check that it is turned on and its USB cable is connected, "
    "then press Reconnect."
)


def no_answer():
    from pydobotlab import DobotTimeoutError

    raise DobotTimeoutError("read timeout")


def test_an_arm_that_does_not_answer_shows_as_disconnected_at_once(
    application, simulated_arm, monkeypatch
):
    from pydobotlab.panel.panel import ControlPanel

    panel = ControlPanel("/dev/sim0")
    try:
        answers = panel._bot.get_device_version
        monkeypatch.setattr(panel._bot, "get_device_version", no_answer)
        panel.check_connection()
        assert not panel._connected
        assert panel._status_label.text() == "● Disconnected"
        assert panel._reconnect_button.isVisibleTo(panel)
        assert not panel._home_button.isEnabled()
        assert panel.statusBar().currentMessage() == NOT_RESPONDING

        monkeypatch.setattr(panel._bot, "get_device_version", answers)
        panel.check_connection()
        assert panel._connected  # it answers again
        assert panel._home_button.isEnabled()

        monkeypatch.setattr(panel._bot, "get_device_version", no_answer)
        for _ in range(3):
            panel.check_connection()
        assert not panel._bot.is_open  # closed after 3 checks in a row without an answer

        monkeypatch.setattr(panel._bot, "get_device_version", answers)
        panel.check_connection()
        assert not panel._connected  # only Reconnect opens it again
        panel.reconnect()
        assert panel._connected and panel._bot.is_open
    finally:
        panel.close()


def test_an_action_is_not_sent_to_an_arm_that_does_not_answer(
    application, simulated_arm, monkeypatch
):
    from pydobotlab import JogMode
    from pydobotlab.panel.panel import ControlPanel

    panel = ControlPanel("/dev/sim0")
    try:
        sent = []
        monkeypatch.setattr(panel._bot, "jog", lambda *arguments: sent.append(arguments))
        monkeypatch.setattr(panel._bot, "jog_stop", lambda: sent.append("stop"))
        monkeypatch.setattr(panel._bot, "get_device_version", no_answer)
        panel.start_jog(1, JogMode.COORDINATE)
        panel.stop_jog()  # the pad's release: no jog was sent, so no stop either
        assert sent == []
        assert not panel._connected
        assert panel.statusBar().currentMessage() == NOT_RESPONDING

        panel.report_stream_error("pose stream: read timeout on '/dev/sim0'")
        assert panel.statusBar().currentMessage() == NOT_RESPONDING  # not the raw error
    finally:
        panel.close()


def test_a_panel_window_never_opens_the_port_itself(application, monkeypatch):
    """Without the panel's broker, a window fails to open instead of taking the
    port, which would make every script find the port busy."""
    import socket

    import serial
    import serial.tools.list_ports

    import pydobotlab.panel.panel as panel_module
    import pydobotlab.simulator as simulator
    from pydobotlab.config import default_config, set_config
    from pydobotlab.transport import is_port_claimed

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        config = default_config()
        config["broker"]["port"] = probe.getsockname()[1]  # no broker there
    set_config(config)
    monkeypatch.setattr(serial, "Serial", serial.Serial)
    monkeypatch.setattr(serial.tools.list_ports, "comports", serial.tools.list_ports.comports)
    monkeypatch.setattr(simulator, "_INSTALLED", False)
    simulator.install_simulator(arms=1)
    failures = []
    monkeypatch.setattr(panel_module.QMessageBox, "critical", lambda *args: failures.append(args))
    try:
        panel = panel_module.ControlPanel("/dev/sim0")
        assert len(failures) == 1
        assert not panel._bot.is_open
        assert not is_port_claimed("/dev/sim0")
        panel.close()
    finally:
        simulator.stop_all()


# -- alarms in the control panel --------------------------------------------------------

LIMIT_POS_J3 = 0x44
OUT_OF_WORKSPACE = 0x11  # PLAN_INVERSE_CALCULATION
FOREARM_LIMIT_TEXT = "The forearm (J3) reached its limit. Jog J3- to move it back."


@pytest.fixture
def simulated_arm(monkeypatch):
    """A simulated arm at /dev/sim0 that control panels open without the broker."""
    import serial
    import serial.tools.list_ports

    import pydobotlab.panel.panel as panel_module
    import pydobotlab.simulator as simulator
    from pydobotlab import Dobot

    monkeypatch.setattr(serial, "Serial", serial.Serial)
    monkeypatch.setattr(serial.tools.list_ports, "comports", serial.tools.list_ports.comports)
    monkeypatch.setattr(simulator, "_INSTALLED", False)
    simulator.install_simulator(arms=1)
    monkeypatch.setattr(
        panel_module, "Dobot", lambda port, **options: Dobot(port, **options, via_broker=False)
    )
    yield simulator.get_or_create_fake("/dev/sim0")
    simulator.stop_all()


def set_alarm(fake, code):
    fake._alarms[code // 8] |= 1 << (code % 8)


def jog_pads(panel):
    return (panel._xy_pad, panel._zr_pad, panel._j12_pad, panel._j34_pad)


def wait_for_homing(application, panel):
    import time

    deadline = time.monotonic() + 15
    while panel._home_worker is not None and time.monotonic() < deadline:
        application.processEvents()
        time.sleep(0.02)
    assert panel._home_worker is None, "homing did not finish"


def test_alarm_banner_is_short_and_the_jog_pads_stay_enabled(application, simulated_arm):
    from pydobotlab.panel.panel import ControlPanel

    panel = ControlPanel("/dev/sim0")
    try:
        panel.update_alarms([LIMIT_POS_J3])
        assert panel._alarm_banner.text() == f"Alarm: {FOREARM_LIMIT_TEXT}"
        assert all(pad.isEnabled() for pad in jog_pads(panel))
    finally:
        panel.close()


def test_developer_banner_shows_names_codes_and_raw_bytes(application, simulated_arm):
    from pydobotlab.panel.panel import ControlPanel

    panel = ControlPanel("/dev/sim0", developer=True)
    try:
        panel.update_alarms([LIMIT_POS_J3])
        text = panel._alarm_banner.text()
        assert "0x44 LIMIT_POS_J3:" in text
        assert "raw alarm bytes: 00 00 00 00 00 00 00 00 10" in text
    finally:
        panel.close()


def test_home_homes_during_an_alarm_with_the_controls_disabled(
    application, simulated_arm, monkeypatch
):
    import pydobotlab.panel.panel as panel_module

    warnings = []
    monkeypatch.setattr(panel_module.QMessageBox, "warning", lambda *args: warnings.append(args))
    panel = panel_module.ControlPanel("/dev/sim0")
    try:
        panel._bot.move_to(250, 50, 30)
        set_alarm(simulated_arm, OUT_OF_WORKSPACE)
        panel.start_homing()
        assert not panel._home_button.isEnabled()
        assert not any(pad.isEnabled() for pad in jog_pads(panel))
        assert not panel._cartesian_readout.isEnabled()  # no typed targets while homing
        wait_for_homing(application, panel)

        assert warnings == []
        assert not panel._bot.get_alarms()
        assert panel.statusBar().currentMessage() == "home complete"
        assert panel._home_button.isEnabled()
        assert all(pad.isEnabled() for pad in jog_pads(panel))
    finally:
        panel.close()


def test_home_never_shows_an_alarm_pop_up(application, simulated_arm, monkeypatch):
    import pydobotlab.panel.panel as panel_module
    from pydobotlab.alarms import decode_alarms, encode_alarms

    warnings = []
    monkeypatch.setattr(panel_module.QMessageBox, "warning", lambda *args: warnings.append(args))
    panel = panel_module.ControlPanel("/dev/sim0")
    try:
        lasting = decode_alarms(encode_alarms([LIMIT_POS_J3]))
        monkeypatch.setattr(panel._bot, "get_alarms", lambda: lasting)
        panel.start_homing()
        wait_for_homing(application, panel)

        assert warnings == []
        assert panel.statusBar().currentMessage() == "home complete - an alarm is still active"
        assert panel._home_button.isEnabled()
    finally:
        panel.close()


# -- typing a target into the pose readout ----------------------------------------------


def test_ptp_target_changes_one_coordinate():
    from pydobotlab import Pose, PTPMode
    from pydobotlab.panel.panel import ptp_target

    pose = Pose(200, 10, 50, 5, 3, 20, 30, 2)
    assert ptp_target(pose, "Z", 80) == (PTPMode.MOVJ_XYZ, (200, 10, 80, 5))
    assert ptp_target(pose, "J2", 40) == (PTPMode.MOVJ_ANGLE, (3, 40, 30, 2))
    with pytest.raises(ValueError, match="unknown coordinate"):
        ptp_target(pose, "L", 1)


def test_a_value_being_typed_stops_following_the_arm(application):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from pydobotlab.panel.widgets import CoordReadout

    readout = CoordReadout(["X", "Y", "Z", "R"])
    readout.show()
    entered = []
    readout.entered.connect(lambda name, value: entered.append((name, value)))
    readout.update_values({"Z": 50})
    field = readout.fields["Z"]
    try:
        QTest.mouseClick(field, Qt.LeftButton)
        field.setText("80.5")
        readout.update_values({"Z": 51})
        assert field.text() == "80.5"  # the typed target stays
        QTest.keyClick(field, Qt.Key_Return)
        assert entered == [("Z", 80.5)]
        assert field.text() == "51.00"  # the arm's value again

        QTest.mouseClick(field, Qt.LeftButton)
        field.setText("-")
        QTest.keyClick(field, Qt.Key_Return)  # not a number: nothing is sent
        QTest.keyClick(field, Qt.Key_Escape)
        assert field.text() == "51.00" and not field.editing
        assert entered == [("Z", 80.5)]
    finally:
        readout.close()


def wait_for_move(application, panel):
    import time

    deadline = time.monotonic() + 15
    while panel._move_worker is not None and time.monotonic() < deadline:
        application.processEvents()
        time.sleep(0.02)
    assert panel._move_worker is None, "the move did not finish"


def rounded_position(bot):
    pose = bot.get_pose()
    return round(pose.x), round(pose.y), round(pose.z)


def test_a_typed_value_moves_the_arm_and_keeps_the_other_coordinates(application, simulated_arm):
    from pydobotlab.panel.panel import ControlPanel

    panel = ControlPanel("/dev/sim0")
    try:
        panel._bot.move_to(200, 0, 50)
        panel._cartesian_readout.entered.emit("Z", 80.0)
        # One move at a time: no typed targets until this one ends.
        assert not panel._cartesian_readout.isEnabled()
        assert not panel._joint_readout.isEnabled()
        wait_for_move(application, panel)

        assert rounded_position(panel._bot) == (200, 0, 80)
        assert panel.statusBar().currentMessage() == "move complete"
        assert panel._cartesian_readout.isEnabled() and panel._joint_readout.isEnabled()
    finally:
        panel.close()


def test_a_typed_joint_angle_moves_with_movj_angle(application, simulated_arm, monkeypatch):
    from pydobotlab import PTPMode
    from pydobotlab.panel.panel import ControlPanel

    panel = ControlPanel("/dev/sim0")
    try:
        moves = []
        monkeypatch.setattr(
            panel._bot, "ptp", lambda mode, *target: moves.append((mode, target)) or True
        )
        pose = panel._bot.get_pose()
        panel._joint_readout.entered.emit("J2", 40.0)
        wait_for_move(application, panel)
        assert moves == [(PTPMode.MOVJ_ANGLE, (pose.j1, 40.0, pose.j3, pose.j4))]
    finally:
        panel.close()


def test_a_typed_target_out_of_reach_shows_the_alarm_without_a_pop_up(
    application, simulated_arm, monkeypatch
):
    import time

    import pydobotlab.panel.panel as panel_module

    warnings = []
    monkeypatch.setattr(panel_module.QMessageBox, "warning", lambda *args: warnings.append(args))
    panel = panel_module.ControlPanel("/dev/sim0")
    try:
        panel._bot.move_to(200, 0, 50)
        panel._cartesian_readout.entered.emit("X", 400.0)
        wait_for_move(application, panel)

        assert rounded_position(panel._bot) == (200, 0, 50)  # the arm did not move
        assert [int(alarm) for alarm in panel._bot.get_alarms()] == [OUT_OF_WORKSPACE]
        assert panel.statusBar().currentMessage() == "the arm refused the move - see the alarm"
        assert warnings == []
        deadline = time.monotonic() + 5
        while not panel._alarm_banner.isVisibleTo(panel) and time.monotonic() < deadline:
            application.processEvents()
            time.sleep(0.02)
        assert panel._alarm_banner.text() == (
            "Alarm: The target is out of reach. Press Clear Alarm and choose a reachable target."
        )
        assert panel._cartesian_readout.isEnabled()  # a new target can be typed
    finally:
        panel.close()


@pytest.mark.parametrize("developer", [False, True])
def test_arms_are_named_by_number_and_ports_shown_in_developer_mode(
    application, simulated_arm, monkeypatch, developer
):
    from pydobotlab import DiscoveredDobot, Discovery
    from pydobotlab.panel.hub import HubWindow

    monkeypatch.setattr(Discovery, "discover_with_diagnostics", staticmethod(lambda: ([], [])))
    hub = HubWindow(developer=developer)
    panel = None
    try:
        hub._worker.wait()
        devices = [DiscoveredDobot("/dev/ttyACM0", "DT1"), DiscoveredDobot("/dev/sim0", "SIM")]
        hub.show_discovery_results(devices)
        hub.show_discovery_results(devices[::-1])  # a scan in another order keeps the names
        expected = ["Dobot Magician 1", "Dobot Magician 2"]
        if developer:
            expected = [
                f"{name}    {device.port}" for name, device in zip(expected, devices, strict=True)
            ]
        assert sorted(listed_rows(hub)[:2]) == expected

        hub.open_panel("/dev/sim0")
        panel = hub._panels["/dev/sim0"]
        title = "Dobot Magician 2  -  /dev/sim0" if developer else "Dobot Magician 2"
        assert panel.windowTitle() == title
        assert panel._title.text() == title
    finally:
        if panel is not None:
            panel.close()
        hub.close()
