"""HubWindow - small device picker that spawns per-arm ControlPanel windows.

Closing the hub closes the whole app; closing a panel only disconnects that
arm and lets the user re-open it from the hub later.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from pydobotlab import Discovery
from pydobotlab.transport import is_port_claimed

from .panel import ControlPanel


class DiscoveryWorker(QThread):
    """Runs Discovery.discover_with_diagnostics() off the GUI thread.

    We use the diagnostic form so the hub can surface ports we *tried* but
    couldn't open - e.g. a /dev/ttyACM0 the current user can't access. The
    plain discover() would drop them silently and the user gets a useless
    "no Dobots found" with no hint to try `sudo usermod -aG dialout $USER`.
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
    """Lists discovered Dobots; clicking 'Open' spawns a ControlPanel."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("pydobotlab - devices")
        self.resize(560, 380)

        self._panels: dict[str, ControlPanel] = {}  # port -> panel
        self._worker: DiscoveryWorker | None = None

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

        self._device_list = QListWidget()
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
            lambda: self._open_button.setEnabled(bool(self._device_list.currentItem()))
        )

        self.setStatusBar(QStatusBar())

    # ---- Discovery ---------------------------------------------------------

    def refresh(self) -> None:
        self.statusBar().showMessage("scanning serial ports...")
        self._refresh_button.setEnabled(False)
        self._device_list.clear()
        self._worker = DiscoveryWorker(self)
        self._worker.finished_with.connect(self.show_discovery_results)
        self._worker.error.connect(self.show_discovery_error)
        self._worker.start()

    def show_discovery_results(self, devices: list, failures: list = None) -> None:
        failures = failures or []
        self._refresh_button.setEnabled(True)
        self._worker = None
        if not devices:
            if failures:
                # Show the ports we did try, with the reason each was rejected.
                # This is the difference between "we couldn't find anything" and
                # "we tried /dev/ttyACM0 but you need sudo to talk to it".
                header = QListWidgetItem("No Dobots answered. Tried these ports:")
                header.setFlags(Qt.NoItemFlags)
                header.setForeground(Qt.gray)
                self._device_list.addItem(header)
                for failure in failures:
                    hint = {
                        "permission": "permission denied - try "
                        "'sudo usermod -aG dialout $USER' then log out & back in",
                        "busy": "port busy - close DobotStudio, another panel, "
                        "or stop brltty: 'sudo systemctl stop brltty'",
                        "no_reply": "opened but didn't answer (wrong device, or arm asleep)",
                        "other": "couldn't open",
                    }.get(failure.reason, failure.reason)
                    item = QListWidgetItem(f"   {failure.port}    {hint}")
                    item.setFlags(Qt.NoItemFlags)
                    item.setForeground(Qt.gray)
                    item.setToolTip(failure.detail)
                    self._device_list.addItem(item)
                self.statusBar().showMessage(
                    f"no Dobots answered; {len(failures)} port(s) tried - hover for details", 6000
                )
            else:
                empty = QListWidgetItem("No Dobots found. Check the USB cable, then click Refresh.")
                empty.setFlags(Qt.NoItemFlags)
                empty.setForeground(Qt.gray)
                self._device_list.addItem(empty)
                self.statusBar().showMessage("no Dobots found", 3000)
            return
        for device in devices:
            label = f"{device.port}    serial: {device.serial_number or '?'}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, device.port)
            if device.port in self._panels and self._panels[device.port].isVisible():
                item.setText(label + "    [panel open]")
                item.setForeground(Qt.gray)
            elif is_port_claimed(device.port):
                item.setText(label + "    [in use elsewhere]")
                item.setForeground(Qt.gray)
            self._device_list.addItem(item)
        self.statusBar().showMessage(f"{len(devices)} device(s) found", 3000)

    def show_discovery_error(self, message: str) -> None:
        self._refresh_button.setEnabled(True)
        self._worker = None
        self.statusBar().showMessage(f"discovery failed: {message}", 5000)

    # ---- Open panel --------------------------------------------------------

    def open_selected_panel(self) -> None:
        item = self._device_list.currentItem()
        if item is None:
            return
        self.open_panel(item.data(Qt.UserRole))

    def open_item_panel(self, item: QListWidgetItem) -> None:
        port = item.data(Qt.UserRole)
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
