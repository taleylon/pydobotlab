"""Per-device control-panel window.

The :class:`ControlPanel` manages one :class:`Dobot` and creates the
DobotLab "Arm Control Panel" interface. It provides jog pads, end-effector
tabs, a speed slider, Home and Clear Alarm buttons, a live pose display, and
an alarm banner. A background pose-stream thread sends updates to the Qt
main thread through :class:`Signal`, ensuring safe label updates.
"""

from __future__ import annotations

import traceback

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pydobotlab import CommandID, Dobot, DobotAlarmError, DobotConnectionError, DobotTimeoutError
from pydobotlab.config import get_config
from pydobotlab.protocol import JOGCmd, JogMode, pack_floats, pack_u8

from .widgets import CoordReadout, JogPad, JumpParamsCard, version_label


def slider_percent(speed_ratio: float) -> int:
    """A velocity ratio as a position of the speed slider (1 to 100)."""
    return max(1, min(100, int(round(speed_ratio))))


# ---------------------------------------------------------------------------
# Background workers
# ---------------------------------------------------------------------------


class PoseStreamer(QObject):
    """Marshals pose-stream callbacks (run in the Dobot worker thread) onto
    the Qt main thread via a signal."""

    poseReady = Signal(float, float, float, float, float, float, float, float)
    alarmsChanged = Signal(list)  # list[str] of alarm names
    speedChanged = Signal(float)  # PTP velocity ratio in percent
    error = Signal(str)

    def __init__(
        self,
        bot: Dobot,
        hz: float = 10.0,
        alarm_hz: float = 2.0,
        speed_hz: float = 1.0,
    ) -> None:
        super().__init__()
        self._bot = bot
        self._hz = hz
        self._alarm_hz = alarm_hz
        self._speed_hz = speed_hz
        self._alarm_period_ticks = max(1, int(round(hz / alarm_hz)))
        self._speed_period_ticks = max(1, int(round(hz / speed_hz)))
        self._tick = 0
        self._last_alarms: list[str] = []
        self._last_speed: float = -1.0

    def push(self, pose) -> None:
        # Called inside Dobot's pose-stream daemon thread.
        try:
            self.poseReady.emit(
                pose.x,
                pose.y,
                pose.z,
                pose.r,
                pose.j1,
                pose.j2,
                pose.j3,
                pose.j4,
            )
            self._tick += 1
            # 2 Hz: alarm refresh.
            # We emit one "{TAG}: {explanation + fix}" line per active alarm
            # so the banner shows both what's wrong and how to recover.
            if self._tick % self._alarm_period_ticks == 0:
                lines = self._bot.get_alarms().format()
                if lines != self._last_alarms:
                    self._last_alarms = lines
                    self.alarmsChanged.emit(lines)
            # 1 Hz: speed refresh - picks up changes a student script
            # makes via motion_params or set_jog_common_params, so the
            # slider stays in sync with what the arm is actually using.
            if self._tick % self._speed_period_ticks == 0:
                try:
                    speed_percent = float(self._bot.get_arm_speed_ratio(1))  # 1 = PTP
                except Exception:
                    speed_percent = self._last_speed
                if abs(speed_percent - self._last_speed) > 0.5:
                    self._last_speed = speed_percent
                    self.speedChanged.emit(speed_percent)
        except Exception as error:
            self.error.emit(f"pose stream: {error}")


class HomeWorker(QThread):
    """Runs ``set_home()`` off the GUI thread so the UI doesn't freeze."""

    done = Signal(bool, str)  # (ok, error_message)

    def __init__(self, bot: Dobot, parent=None) -> None:
        super().__init__(parent)
        self._bot = bot

    def run(self) -> None:
        try:
            self._bot.set_home()
            self.done.emit(True, "")
        except DobotAlarmError as error:
            self.done.emit(False, str(error))  # the message lists each alarm and its fix
        except Exception as error:
            self.done.emit(False, f"{error}\n{traceback.format_exc()}")


# ---------------------------------------------------------------------------
# ControlPanel main window
# ---------------------------------------------------------------------------


class ControlPanel(QMainWindow):
    """One window per arm - DobotLab Arm Control Panel look & feel."""

    closed = Signal(str)  # emits port name when window closes

    def __init__(self, port: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Dobot Magician @ {port}")
        self.resize(880, 760)

        self._port = port
        self._bot = Dobot(port)
        self._streamer: PoseStreamer | None = None
        self._home_worker: HomeWorker | None = None
        self._connected: bool = False
        self._jog_locked: bool = False  # True while alarms are active
        self._watchdog: QTimer | None = None
        self._failed_checks: int = 0  # consecutive failed watchdog checks

        self.build_ui()
        self.connect_signals()

        # Defer connection so the window can show "connecting..." first.
        self.statusBar().showMessage(f"Connecting to {port}...")
        # Single-shot via a 0-ms QThread-style; here just call directly since
        # connect() is fast for the happy path.
        self.connect_to_arm()

    # ---- UI ----------------------------------------------------------------

    def build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # Header: port + serial + status + Reconnect + Home + Clear Alarm
        header = QHBoxLayout()
        self._title = QLabel(f"Dobot Magician  -  {self._port}")
        self._title.setObjectName("header")
        header.addWidget(self._title)
        header.addStretch(1)
        self._status_label = QLabel("● Connected")
        self._status_label.setStyleSheet("color:#7ce070; font-weight:600;")
        header.addWidget(self._status_label)
        self._reconnect_button = QPushButton("Reconnect")
        self._reconnect_button.setVisible(False)
        header.addWidget(self._reconnect_button)
        self._home_button = QPushButton("Home")
        self._home_button.setObjectName("primary")
        self._clear_alarm_button = QPushButton("Clear Alarm")
        header.addWidget(self._home_button)
        header.addWidget(self._clear_alarm_button)
        root.addLayout(header)

        # Alarm banner (hidden when empty)
        self._alarm_banner = QLabel("")
        self._alarm_banner.setObjectName("alarmBanner")
        self._alarm_banner.setVisible(False)
        root.addWidget(self._alarm_banner)

        # Speed slider
        speed_card = QFrame()
        speed_card.setObjectName("card")
        speed_box = QHBoxLayout(speed_card)
        speed_box.setContentsMargins(12, 8, 12, 8)
        speed_lbl = QLabel("Speed")
        speed_lbl.setStyleSheet("color:#aab2c2; font-weight:600;")
        self._speed_slider = QSlider(Qt.Horizontal)
        self._speed_slider.setRange(1, 100)
        self._speed_slider.setValue(50)
        self._speed_slider.setSingleStep(1)
        self._speed_slider.setPageStep(10)
        self._speed_value = QLabel("50 %")
        self._speed_value.setStyleSheet("color:#6cc6ff; min-width:48px;")
        speed_box.addWidget(speed_lbl)
        speed_box.addWidget(self._speed_slider, stretch=1)
        speed_box.addWidget(self._speed_value)
        root.addWidget(speed_card)

        # Jump-mode parameters (zlimit + height) - surfaced on the panel
        # because DobotLab keeps them hidden behind a menu.
        self._jump_card = JumpParamsCard()
        root.addWidget(self._jump_card)

        # Two coordinate readouts - Cartesian for the top row, joints for
        # the bottom row. Each sits next to its corresponding jog pads in a
        # single horizontal row so the numbers stay visually associated with
        # the controls that move them (matches the DobotLab layout exactly).
        self._cartesian_readout = CoordReadout(["X", "Y", "Z", "R"])
        self._joint_readout = CoordReadout(["J1", "J2", "J3", "J4"])

        # Layout copied from the Windows DobotLab arm control panel.
        # fmt: off
        self._xy_pad = JogPad(
            "X / Y",
            {
                "top"       : ("X+", JOGCmd.AP_DOWN),
                "bottom"    : ("X-", JOGCmd.AN_DOWN),
                "left"      : ("Y-", JOGCmd.BN_DOWN),
                "right"     : ("Y+", JOGCmd.BP_DOWN),
            },
        )
        self._zr_pad = JogPad(
            "Z / R",
            {
                "top"       : ("Z+", JOGCmd.CP_DOWN),
                "bottom"    : ("Z-", JOGCmd.CN_DOWN),
                "left"      : ("R-", JOGCmd.DN_DOWN),
                "right"     : ("R+", JOGCmd.DP_DOWN),
            },
        )
        self._j12_pad = JogPad(
            "J1 / J2",
            {
                "top_left"      : ("J1-", JOGCmd.AN_DOWN),
                "top_right"     : ("J1+", JOGCmd.AP_DOWN),
                "bottom_left"   : ("J2-", JOGCmd.BN_DOWN),
                "bottom_right"  : ("J2+", JOGCmd.BP_DOWN),
            },
        )
        self._j34_pad = JogPad(
            "J3 / J4",
            {
                "top_left"      : ("J3-", JOGCmd.CN_DOWN),
                "top_right"     : ("J3+", JOGCmd.CP_DOWN),
                "bottom_left"   : ("J4-", JOGCmd.DN_DOWN),
                "bottom_right"  : ("J4+", JOGCmd.DP_DOWN),
            },
        )
        # fmt: on

        # Cartesian row: [X/Y/Z/R readout | X/Y pad | Z/R pad]
        cart_row = QHBoxLayout()
        cart_row.setSpacing(10)
        cart_row.addWidget(self._cartesian_readout)
        cart_row.addWidget(self._xy_pad, stretch=1)
        cart_row.addWidget(self._zr_pad, stretch=1)
        root.addLayout(cart_row, stretch=1)

        # Joint row: [J1..J4 readout | J1/J2 pad | J3/J4 pad]
        joint_row = QHBoxLayout()
        joint_row.setSpacing(10)
        joint_row.addWidget(self._joint_readout)
        joint_row.addWidget(self._j12_pad, stretch=1)
        joint_row.addWidget(self._j34_pad, stretch=1)
        root.addLayout(joint_row, stretch=1)

        # End effector tabs
        self._effector = self.build_end_effector_tabs()
        root.addWidget(self._effector)

        self.setStatusBar(QStatusBar())
        self._version_label = version_label()
        self.statusBar().addPermanentWidget(self._version_label)

    def build_end_effector_tabs(self) -> QTabWidget:
        tabs = QTabWidget()

        def make_tab(title: str, on_change) -> QWidget:
            widget = QWidget()
            box = QHBoxLayout(widget)
            box.setContentsMargins(16, 12, 16, 12)
            box.setSpacing(20)
            enable_cb = QCheckBox("Enable")
            on_cb = QCheckBox("On")
            enable_cb.toggled.connect(
                lambda _checked: on_change(enable_cb.isChecked(), on_cb.isChecked())
            )
            on_cb.toggled.connect(
                lambda _checked: on_change(enable_cb.isChecked(), on_cb.isChecked())
            )
            box.addWidget(enable_cb)
            box.addWidget(on_cb)
            box.addStretch(1)
            return widget

        # Closures capture 'self'.
        suction_w = make_tab("Suction", self.set_suction)
        gripper_w = make_tab("Gripper", self.set_gripper)
        laser_w = make_tab("Laser", self.set_laser)
        tabs.addTab(suction_w, "Suction Cup")
        tabs.addTab(gripper_w, "Gripper")
        tabs.addTab(laser_w, "Laser")
        return tabs

    # ---- Signal wiring ------------------------------------------------------

    def connect_signals(self) -> None:
        self._home_button.clicked.connect(self.start_homing)
        self._clear_alarm_button.clicked.connect(self.clear_alarms)
        self._reconnect_button.clicked.connect(self.reconnect)
        self._jump_card.valuesChanged.connect(self.apply_jump_params)
        self._speed_slider.valueChanged.connect(self.update_speed_label)
        self._speed_slider.sliderReleased.connect(self.apply_speed)

        for pad in (self._xy_pad, self._zr_pad):
            pad.jog.connect(lambda c: self.start_jog(c, JogMode.COORDINATE))
            pad.stop.connect(self.stop_jog)
        for pad in (self._j12_pad, self._j34_pad):
            pad.jog.connect(lambda c: self.start_jog(c, JogMode.JOINT))
            pad.stop.connect(self.stop_jog)

    # ---- Connection lifecycle ----------------------------------------------

    def connect_to_arm(self) -> None:
        try:
            self._bot.connect()
        except DobotConnectionError as error:
            QMessageBox.critical(
                self, "Connection failed", f"Could not open {self._port}:\n{error}"
            )
            self.close()
            return

        self._title.setText(f"Dobot Magician  -  {self._bot.port}")
        self.statusBar().showMessage(f"Connected to {self._bot.port}")

        self.adopt_arm_speed()

        # Pull the current Jump params so the card matches the firmware.
        try:
            zlimit, height = self._bot.jump_params
            self._jump_card.update_values(zlimit, height)
        except Exception:
            pass

        # Watchdog: poke the arm at a fixed interval and update the connection
        # indicator. If the cable is unplugged, this is what notices.
        settings = get_config()["panel"]
        if self._watchdog is None:
            self._watchdog = QTimer(self)
            self._watchdog.setInterval(round(settings["watchdog_interval"] * 1000))
            self._watchdog.timeout.connect(self.check_connection)
        self._watchdog.start()
        self.set_connection_state(True)

        self.start_streaming()

    def start_streaming(self) -> None:
        """Start the pose stream that drives the readout and the alarm banner."""
        settings = get_config()["panel"]
        self._streamer = PoseStreamer(
            self._bot, hz=settings["pose_hz"], alarm_hz=settings["alarm_hz"]
        )
        self._streamer.poseReady.connect(self.update_pose)
        self._streamer.alarmsChanged.connect(self.update_alarms)
        self._streamer.speedChanged.connect(self.sync_speed)
        self._streamer.error.connect(lambda message: self.statusBar().showMessage(message, 3000))
        self._bot.start_pose_stream(
            callback=self._streamer.push,
            hz=settings["pose_hz"],
            on_error=lambda error: self._streamer.error.emit(f"pose stream: {error}"),
        )

    def closeEvent(self, event) -> None:
        try:
            if self._home_worker is not None and self._home_worker.isRunning():
                self._home_worker.requestInterruption()
                self._home_worker.wait(2000)
            self._bot.disconnect()
        finally:
            self.closed.emit(self._port)
            event.accept()

    # ---- Slots --------------------------------------------------------------

    @Slot(int)
    def start_jog(self, cmd: int, mode: JogMode) -> None:
        try:
            self._bot.jog(cmd, mode)
        except Exception as error:
            self.statusBar().showMessage(f"jog: {error}", 3000)

    @Slot()
    def stop_jog(self) -> None:
        try:
            self._bot.jog_stop()
        except Exception as error:
            self.statusBar().showMessage(
                f"STOP FAILED - the arm may still be moving: {error}", 10000
            )

    @Slot(int)
    def update_speed_label(self, value: int) -> None:
        self._speed_value.setText(f"{value} %")

    @Slot()
    def apply_speed(self) -> None:
        """Push the slider value to BOTH PTP and JOG so jog buttons honour
        the speed setting just like move_to() does. Sent immediately, so it
        applies to a running script's next move without waiting for it."""
        speed_percent = float(self._speed_slider.value())
        ratios = pack_floats(speed_percent, speed_percent)
        try:
            self._bot.write_command(CommandID.GET_SET_PTP_COMMON_PARAMS, ratios)
            self._bot.write_command(CommandID.GET_SET_JOG_COMMON_PARAMS, ratios)
        except Exception as error:
            self.statusBar().showMessage(f"speed: {error}", 3000)

    @Slot()
    def start_homing(self) -> None:
        if self._home_worker is not None and self._home_worker.isRunning():
            return
        self._home_button.setEnabled(False)
        self.statusBar().showMessage("homing...")
        self._home_worker = HomeWorker(self._bot, self)
        self._home_worker.done.connect(self.finish_homing)
        self._home_worker.start()

    @Slot(bool, str)
    def finish_homing(self, ok: bool, error: str) -> None:
        self._home_button.setEnabled(True)
        self._home_worker = None
        if ok:
            self.statusBar().showMessage("home complete", 3000)
        else:
            self.statusBar().showMessage("home failed", 3000)
            QMessageBox.warning(self, "Home failed", error)

    @Slot()
    def clear_alarms(self) -> None:
        """Clear the alarms; if one comes back at once, keep it and say why.

        ``clear_alarm()`` re-reads the alarms after a short settle and raises
        when the cause is still present (a joint against its limit, a
        faulting sensor, ...), so the student never sees a misleading
        "alarms cleared" message.
        """
        try:
            self._bot.clear_alarm()
        except DobotAlarmError as error:
            QMessageBox.warning(self, "Alarm persists", str(error))
            self.statusBar().showMessage("alarm persists - see warning", 4000)
            return
        except Exception as error:
            QMessageBox.warning(self, "Clear alarm failed", str(error))
            return
        self.statusBar().showMessage("alarms cleared", 2000)
        self._alarm_banner.setVisible(False)

    @Slot(list)
    def update_alarms(self, lines: list) -> None:
        """Display each active alarm; lock out JOG while alarms are active.

        Why lock JOG out: in alarm state the firmware queue is paused, and
        some firmware revisions ignore the JOG-IDLE on button release even
        though we send it as an IMMEDIATE frame. The visible symptom is
        "click a button, the arm keeps moving forever". The safe behaviour
        is to refuse to start a new jog at all until the student clears the
        alarm (which the panel surfaces with the troubleshoot text right
        above the buttons). Clear Alarm stays enabled - it is the recovery
        path. Home stays enabled and reports the active alarm.

        We also fire one extra ``jog_stop()`` on every transition, so if a
        jog was already in flight at the moment the alarm fired, the arm
        stops the moment we see the alarm.
        """
        active = bool(lines)
        if active:
            text = "\n".join(f"  • {line}" for line in lines)
            self._alarm_banner.setText("ALARMS:\n" + text)
            self._alarm_banner.setVisible(True)
        else:
            self._alarm_banner.setVisible(False)
        # Toggle JOG availability (Clear Alarm stays on - it recovers).
        if active != self._jog_locked:
            self._jog_locked = active
            for pad in (self._xy_pad, self._zr_pad, self._j12_pad, self._j34_pad):
                pad.setEnabled(not active)
            if active:
                # Belt-and-braces: any jog that was in flight when the alarm
                # fired is forcibly idled now, so the arm stops with the alarm.
                try:
                    self._bot.jog_stop()
                except Exception as error:
                    self.statusBar().showMessage(
                        f"Attention! stop has failed - the arm may still be moving: {error}", 10000
                    )
                else:
                    self.statusBar().showMessage(
                        "Attention! Jog is disabled - you must clear the alarm first",
                        4000,
                    )

    @Slot(float, float, float, float, float, float, float, float)
    def update_pose(
        self, x: float, y: float, z: float, r: float, j1: float, j2: float, j3: float, j4: float
    ) -> None:
        """Fan a single pose-stream tick out to the two coord readouts."""
        self._cartesian_readout.update_values({"X": x, "Y": y, "Z": z, "R": r})
        self._joint_readout.update_values({"J1": j1, "J2": j2, "J3": j3, "J4": j4})

    # ---- Connection watchdog & reconnect ------------------------------------

    @Slot()
    def check_connection(self) -> None:
        """Probe TRANSPORT HEALTH - does the wire still answer?

        We use ``get_device_version()`` rather than something arm-state-y like
        ``get_alarms()`` because:

        * it is a pure read with no side-effects on motion or alarms;
        * it cannot raise as a consequence of any logical state on the arm
          (an active workspace / IK alarm does not affect the read);
        * the ONLY way it can fail is if the serial transport itself died.

        Likewise we catch only the two transport exceptions. Any other
        exception (bug, programming error, ...) is allowed to propagate so
        we don't mistakenly interpret a logic problem as a cable pull.
        """
        if not self._connected:
            return
        try:
            self._bot.get_device_version()
        except (DobotConnectionError, DobotTimeoutError):
            self._failed_checks += 1
            if self._failed_checks >= get_config()["panel"]["watchdog_failures"]:
                self.set_connection_state(False)
            else:
                self.statusBar().showMessage("connecting...", 4000)
        else:
            self._failed_checks = 0

    def set_connection_state(self, connected: bool) -> None:
        if connected == self._connected:
            return
        self._connected = connected
        self._failed_checks = 0
        if connected:
            self._status_label.setText("● Connected")
            self._status_label.setStyleSheet("color:#7ce070; font-weight:600;")
            self._reconnect_button.setVisible(False)
        else:
            self._status_label.setText("● Disconnected")
            self._status_label.setStyleSheet("color:#ff6b6b; font-weight:600;")
            self._reconnect_button.setVisible(True)
            # Stop the pose stream so it stops error-spamming the log.
            try:
                self._bot.stop_pose_stream()
            except Exception:
                pass
        # Disable interactive controls while offline.
        for widget in (
            self._home_button,
            self._clear_alarm_button,
            self._xy_pad,
            self._zr_pad,
            self._j12_pad,
            self._j34_pad,
            self._speed_slider,
            self._jump_card,
            self._effector,
        ):
            widget.setEnabled(connected)

    @Slot()
    def reconnect(self) -> None:
        """Try to re-open the serial connection to the same port."""
        self._reconnect_button.setEnabled(False)
        self.statusBar().showMessage(f"Reconnecting to {self._port}...")
        try:
            try:
                self._bot.disconnect()
            except Exception:
                pass
            self._bot.connect()
        except Exception as error:
            self.statusBar().showMessage(f"Reconnect failed: {error}", 5000)
            self._reconnect_button.setEnabled(True)
            return
        # Restart the pose stream + watchdog
        self.start_streaming()
        self.adopt_arm_speed()
        self.set_connection_state(True)
        self._reconnect_button.setEnabled(True)
        self.statusBar().showMessage(f"Reconnected to {self._port}", 3000)

    # ---- Jump-params card --------------------------------------------------

    @Slot(float, float)
    def apply_jump_params(self, zlimit: float, height: float) -> None:
        try:
            # Wire order is (jumpHeight, zLimit).
            self._bot.write_command(
                CommandID.GET_SET_PTP_JUMP_PARAMS, pack_floats(float(height), float(zlimit))
            )
        except Exception as error:
            self.statusBar().showMessage(f"jump_params: {error}", 3000)

    def show_speed(self, speed_percent: int) -> None:
        """Move the slider without emitting signals, so nothing is sent back to the arm."""
        self._speed_slider.blockSignals(True)
        try:
            self._speed_slider.setValue(speed_percent)
        finally:
            self._speed_slider.blockSignals(False)
        self._speed_value.setText(f"{speed_percent} %")

    def apply_jog_speed(self, speed_percent: float) -> None:
        try:
            self._bot.write_command(
                CommandID.GET_SET_JOG_COMMON_PARAMS,
                pack_floats(float(speed_percent), float(speed_percent)),
            )
        except Exception as error:
            self.statusBar().showMessage(f"speed: {error}", 3000)

    def adopt_arm_speed(self) -> None:
        """Take over the speed the arm already has, so opening the panel does not
        change the speed of a running script. Jogging uses the same speed."""
        try:
            speed_percent = slider_percent(self._bot.get_arm_speed_ratio(1))  # 1 = PTP
        except Exception as error:
            self.statusBar().showMessage(f"speed: {error}", 3000)
            return
        self.show_speed(speed_percent)
        self.apply_jog_speed(speed_percent)

    @Slot(float)
    def sync_speed(self, vel: float) -> None:
        """A script (or another panel) changed the arm's speed: show it on the
        slider and use it for jogging too."""
        speed_percent = slider_percent(vel)
        if self._speed_slider.value() == speed_percent:
            return
        self.show_speed(speed_percent)
        self.apply_jog_speed(speed_percent)

    # ---- End-effector handlers ---------------------------------------------
    # Sent immediately, so a button acts at once even while a script's move
    # is running, and the GUI thread never waits for the arm's queue.

    def set_end_effector(self, command_id: CommandID, enable: bool, on: bool, label: str) -> None:
        try:
            self._bot.write_command(command_id, pack_u8(int(enable), int(on)))
        except Exception as error:
            self.statusBar().showMessage(f"{label}: {error}", 3000)

    def set_suction(self, enable: bool, on: bool) -> None:
        self.set_end_effector(CommandID.GET_SET_END_EFFECTOR_SUCTION_CUP, enable, on, "suction")

    def set_gripper(self, enable: bool, on: bool) -> None:
        self.set_end_effector(CommandID.GET_SET_END_EFFECTOR_GRIPPER, enable, on, "gripper")

    def set_laser(self, enable: bool, on: bool) -> None:
        self.set_end_effector(CommandID.GET_SET_END_EFFECTOR_LASER, enable, on, "laser")
