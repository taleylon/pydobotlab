"""Device hub for launching a separate ControlPanel window for each arm.

Closing the hub exits the application, after asking when scripts are connected
through it. Closing an individual panel disconnects only its arm and allows the
panel to be reopened from the hub.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pydobotlab import Discovery
from pydobotlab.broker import DobotBroker
from pydobotlab.transport import is_port_claimed

from .panel import ControlPanel
from .panel_config import PANEL_CONFIG
from .widgets import version_label

HUB_TEXT = PANEL_CONFIG["hub"]


class DiscoveryWorker(QThread):
    """Runs Discovery.discover_with_diagnostics() off the GUI thread.

    We use the diagnostic form so the hub can surface ports we *tried* but
    couldn't open - e.g. a /dev/ttyACM0 the current user can't access. The
    plain discover() would drop them silently and the user gets a useless
    "no devices found" with no hint to try `sudo usermod -aG dialout $USER`.
    """

    finished_with = Signal(list, list)  # (hits, failures)
    error = Signal(str)

    def run(self) -> None:
        try:
            devices, failures = Discovery.discover_with_diagnostics()
            self.finished_with.emit(devices, failures)
        except Exception as error:
            self.error.emit(str(error))


class HubWindow(QMainWindow):
    """Lists discovered Dobot Magicians; clicking 'Open' spawns a ControlPanel."""

    def __init__(
        self, parent=None, *, developer: bool = False, broker: DobotBroker | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("pydobotlab - devices")
        self.resize(560, 380)

        self._developer = developer  # show ports; passed on to each control panel
        self._broker = broker  # the broker this app started and stops on quit, if any
        self._panels: dict[str, ControlPanel] = {}  # port -> panel
        self._numbers: dict[str, int] = {}  # port -> number in "Dobot Magician <number>"
        self._worker: DiscoveryWorker | None = None  # the running scan, if any
        self._rescan_requested: bool = False  # refresh() was called during a scan

        self.build_ui()
        self.refresh()

    # ---- UI ----------------------------------------------------------------

    def build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Dobot Magicians on this computer")
        title.setObjectName("header")
        header.addWidget(title)
        header.addStretch(1)
        self._refresh_button = QPushButton("Refresh")
        self._refresh_button.clicked.connect(self.refresh)
        header.addWidget(self._refresh_button)
        root.addLayout(header)

        # Messages too long for a row of the list, such as the permission
        # problem, wrap in this box above it.
        self._notice = QLabel()
        self._notice.setObjectName("notice")
        self._notice.setWordWrap(True)
        self._notice.setVisible(False)
        root.addWidget(self._notice)

        self._device_list = QTreeWidget()
        self._device_list.setHeaderHidden(True)
        self._device_list.setExpandsOnDoubleClick(False)
        self._device_list.itemClicked.connect(self.toggle_group)
        self._device_list.itemDoubleClicked.connect(self.open_item_panel)
        root.addWidget(self._device_list, stretch=1)

        actions = QHBoxLayout()
        self._open_button = QPushButton("Open Control Panel")
        self._open_button.setObjectName("primary")
        self._open_button.setEnabled(False)
        self._open_button.clicked.connect(self.open_selected_panel)
        actions.addStretch(1)
        actions.addWidget(self._open_button)
        root.addLayout(actions)

        self._device_list.itemSelectionChanged.connect(
            lambda: self._open_button.setEnabled(self.selected_port() is not None)
        )

        self.setStatusBar(QStatusBar())
        self._version_label = version_label()
        self.statusBar().addPermanentWidget(self._version_label)

    # ---- Discovery ---------------------------------------------------------

    def refresh(self) -> None:
        # One scan at a time: two scans would open the same ports at once, and
        # each would see the ports the other holds as busy.
        if self._worker is not None:
            self._rescan_requested = True
            return
        self.statusBar().showMessage("scanning serial ports...")
        self._refresh_button.setEnabled(False)
        self._device_list.clear()
        self._worker = DiscoveryWorker(self)
        self._worker.finished_with.connect(self.show_discovery_results)
        self._worker.error.connect(self.show_discovery_error)
        self._worker.start()

    def finish_scan(self) -> bool:
        """End the current scan; ``False`` if a requested re-scan replaces its results."""
        self._worker = None
        if self._rescan_requested:
            self._rescan_requested = False
            self.refresh()
            return False
        self._refresh_button.setEnabled(True)
        self._device_list.clear()
        self._notice.setVisible(False)
        return True

    def device_name(self, port: str) -> str:
        """``Dobot Magician <number>``, numbered in the order the arms are first found.
        A port keeps its number for the session."""
        if port not in self._numbers:
            self._numbers[port] = len(self._numbers) + 1
        return f"Dobot Magician {self._numbers[port]}"

    def device_label(self, port: str) -> str:
        """The arm's row in the list: its name, and its port in developer mode."""
        name = self.device_name(port)
        return f"{name}    {port}" if self._developer else name

    def add_note(self, text: str, tooltip: str = "", parent=None) -> QTreeWidgetItem:
        """Add a grey row that cannot be selected, under ``parent`` or at the top level."""
        item = QTreeWidgetItem([text])
        item.setFlags(Qt.NoItemFlags)
        item.setForeground(0, Qt.gray)
        item.setToolTip(0, tooltip)
        if parent is None:
            self._device_list.addTopLevelItem(item)
        else:
            parent.addChild(item)
        return item

    def show_discovery_results(self, devices: list, failures: list = None) -> None:
        if not self.finish_scan():
            return
        failures = failures or []
        other_devices = [failure for failure in failures if failure.reason == "no_reply"]
        open_failures = [failure for failure in failures if failure.reason != "no_reply"]

        for device in devices:
            label = self.device_label(device.port)
            item = QTreeWidgetItem([label])
            item.setData(0, Qt.UserRole, device.port)
            if device.port in self._panels and self._panels[device.port].isVisible():
                item.setText(0, f"{label}    [panel open]")
                item.setForeground(0, Qt.gray)
            elif is_port_claimed(device.port):
                item.setText(0, f"{label}    [in use elsewhere]")
                item.setForeground(0, Qt.gray)
            self._device_list.addTopLevelItem(item)

        if not devices:
            self.show_not_found(open_failures)
        # Without a Dobot Magician, only developer mode lists the ports that were tried.
        if devices or self._developer:
            self.add_other_devices(other_devices)

        not_found = HUB_TEXT["not_found"]
        if devices:
            num_of_devices = len(devices)
            device_str = "device" if num_of_devices == 1 else "devices"
            self.statusBar().showMessage(
                f"{num_of_devices} Dobot Magician {device_str} found", 3000
            )
        elif failures and self._developer:
            self.statusBar().showMessage(
                not_found["status_ports_tried"].format(count=len(failures)), 6000
            )
        else:
            self.statusBar().showMessage(not_found["status"], 3000)

    def show_not_found(self, open_failures: list) -> None:
        """Say that no Dobot Magician was found, and why when it is known.

        ``open_failures`` are the ports that could not be opened; one of them
        may hold a Magician. Developer mode lists each of them.
        """
        not_found = HUB_TEXT["not_found"]
        busy = any(failure.reason == "busy" for failure in open_failures)
        note = not_found["note"]
        if busy and not self._developer:
            note += "\n" + not_found["busy"]
        self.add_note(note)
        # Permission failures share one cause (e.g. missing dialout group), so the
        # explanation is shown once instead of once per port.
        permission_failures = [f for f in open_failures if f.reason == "permission"]
        if permission_failures:
            text = permission_failures[0].detail
            if self._developer:
                ports = ", ".join(f.port for f in permission_failures)
                text += "\n" + not_found["affected_ports"].format(ports=ports)
            self._notice.setText(text)
            self._notice.setVisible(True)
        if not self._developer:
            return
        for failure in open_failures:
            if failure.reason == "permission":
                continue
            hint = HUB_TEXT["port_problems"].get(failure.reason, failure.reason)
            self.add_note(f"{failure.port}    {hint}", failure.detail)

    def add_other_devices(self, other_devices: list) -> None:
        """A line, then the ports that answered, but not as a Dobot Magician, collapsed."""
        separator = QTreeWidgetItem()
        separator.setFlags(Qt.NoItemFlags)
        separator.setSizeHint(0, QSize(0, 9))
        self._device_list.addTopLevelItem(separator)
        line = QFrame()
        line.setObjectName("separator")
        line.setFixedHeight(1)
        self._device_list.setItemWidget(separator, 0, line)

        group = QTreeWidgetItem([f"Other devices ({len(other_devices)})"])
        group.setFlags(Qt.ItemIsEnabled)
        group.setForeground(0, Qt.gray)
        self._device_list.addTopLevelItem(group)
        for failure in other_devices:
            description = failure.description.removesuffix(f" ({failure.port})")
            text = f"{failure.port}    {description}" if description else failure.port
            self.add_note(text, failure.detail, parent=group)

    def show_discovery_error(self, message: str) -> None:
        if not self.finish_scan():
            return
        self.statusBar().showMessage(f"discovery failed: {message}", 5000)

    # ---- Open panel --------------------------------------------------------

    def selected_port(self) -> str | None:
        """Port of the selected Dobot Magician, or ``None``."""
        item = self._device_list.currentItem()
        return item.data(0, Qt.UserRole) if item is not None else None

    def toggle_group(self, item: QTreeWidgetItem, column: int = 0) -> None:
        if item.childCount():
            item.setExpanded(not item.isExpanded())

    def open_selected_panel(self) -> None:
        port = self.selected_port()
        if port:
            self.open_panel(port)

    def open_item_panel(self, item: QTreeWidgetItem, column: int = 0) -> None:
        port = item.data(0, Qt.UserRole)
        if port:
            self.open_panel(port)

    def open_panel(self, port: str) -> None:
        if port in self._panels and self._panels[port].isVisible():
            self._panels[port].raise_()
            self._panels[port].activateWindow()
            return
        try:
            panel = ControlPanel(  # top-level
                port, parent=None, developer=self._developer, name=self.device_name(port)
            )
        except Exception as error:
            QMessageBox.critical(self, "Open failed", f"Could not open {port}:\n{error}")
            return
        panel.closed.connect(self.remove_panel)
        self._panels[port] = panel
        panel.show()

    def remove_panel(self, port: str) -> None:
        self._panels.pop(port, None)
        # Refresh list so any "[panel open]" tags update.
        self.refresh()

    # ---- Hub close = quit app ---------------------------------------------

    def script_count(self) -> int:
        """Scripts connected to an arm through this app's broker."""
        if self._broker is None:
            return 0
        # Each connected panel window holds one broker connection; the other
        # clients are scripts.
        panel_count = sum(1 for panel in self._panels.values() if panel.has_open_connection)
        return max(0, self._broker.client_count() - panel_count)

    def confirm_quit(self, script_count: int) -> bool:
        dialog = HUB_TEXT["quit_dialog"]
        text = dialog["one_script"] if script_count == 1 else dialog["several_scripts"]
        answer = QMessageBox.question(
            self,
            dialog["title"],
            text.format(count=script_count),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return answer == QMessageBox.Yes

    def closeEvent(self, event) -> None:
        script_count = self.script_count()
        if script_count and not self.confirm_quit(script_count):
            event.ignore()
            return
        for panel in list(self._panels.values()):
            panel.close()
        event.accept()
