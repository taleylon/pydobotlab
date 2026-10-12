"""Device hub for launching a separate ControlPanel window for each arm.

Closing the hub exits the application. Closing an individual panel disconnects
only its arm and allows the panel to be reopened from the hub.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
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
from pydobotlab.transport import is_port_claimed

from .panel import ControlPanel
from .widgets import version_label


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

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("pydobotlab - devices")
        self.resize(560, 380)

        self._panels: dict[str, ControlPanel] = {}  # port -> panel
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
        return True

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
            item = QTreeWidgetItem([device.port])
            item.setData(0, Qt.UserRole, device.port)
            if device.port in self._panels and self._panels[device.port].isVisible():
                item.setText(0, f"{device.port}    [panel open]")
                item.setForeground(0, Qt.gray)
            elif is_port_claimed(device.port):
                item.setText(0, f"{device.port}    [in use elsewhere]")
                item.setForeground(0, Qt.gray)
            self._device_list.addTopLevelItem(item)

        if not devices:
            self.add_note(
                "No Dobot Magician devices were found.\n"
                "Check the USB cable and power, then click Refresh."
            )
            # A port that could not be opened may still hold a Magician. Permission
            # failures share one cause (e.g. missing dialout group), so the
            # explanation is shown once instead of once per port.
            permission_failures = [f for f in open_failures if f.reason == "permission"]
            if permission_failures:
                ports = ", ".join(f.port for f in permission_failures)
                self.add_note(permission_failures[0].detail, f"Affected ports: {ports}")
            for failure in open_failures:
                if failure.reason == "permission":
                    continue
                hint = {"busy": "port is busy", "other": "couldn't open"}.get(
                    failure.reason, failure.reason
                )
                self.add_note(f"{failure.port}    {hint}", failure.detail)

        # Ports that answered, but not as a Dobot Magician: collapsed by default.
        group = QTreeWidgetItem([f"Other devices ({len(other_devices)})"])
        group.setFlags(Qt.ItemIsEnabled)
        group.setForeground(0, Qt.gray)
        self._device_list.addTopLevelItem(group)
        for failure in other_devices:
            description = failure.description.removesuffix(f" ({failure.port})")
            text = f"{failure.port}    {description}" if description else failure.port
            self.add_note(text, failure.detail, parent=group)

        if devices:
            num_of_devices = len(devices)
            device_str = "device" if num_of_devices == 1 else "devices"
            self.statusBar().showMessage(f"{num_of_devices} Dobot Magician {device_str} found", 3000)
        elif failures:
            num_of_failures = len(failures)
            failure_str = "port" if num_of_failures == 1 else "ports"
            self.statusBar().showMessage(
                f"no Dobot Magician devices found; {len(failures)} {failure_str} tried"
                " - hover for details",
                6000,
            )
        else:
            self.statusBar().showMessage("no Dobot Magician devices found", 3000)

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
            panel = ControlPanel(port, parent=None)  # top-level, not a child
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

    def closeEvent(self, event) -> None:
        for panel in list(self._panels.values()):
            panel.close()
        event.accept()
