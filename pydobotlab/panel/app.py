"""Entry point for the pydobotlab control-panel GUI.

Enables the option to run it through the ``pydobotlab-panel`` console script after installing
``pip install pydobotlab[gui]``, or with ``python -m pydobotlab.panel``.

Desktop shortcut
----------------

    pydobotlab-panel --create-shortcut            # desktop icon and menu entry

Simulator mode
--------------

    pydobotlab-panel --simulator                  # 2 fake arms, no hardware needed
    pydobotlab-panel --simulator --simulator-arms 4

Simulator mode allows you to inspect or debug the panel without a physical
Dobot device connected. It replaces the serial backend while
keeping the broker, hub, control panel, jog, home, pose-stream, and
end-effector tabs unchanged. Simulated arms move at 30 Hz, allowing continuous pose-stream.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def load_stylesheet() -> str:
    try:
        return (Path(__file__).parent / "style.qss").read_text(encoding="utf-8")
    except OSError:
        return ""


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pydobotlab-panel",
        description="pydobotlab control-panel GUI (DobotLab replacement).",
    )
    parser.add_argument(
        "--simulator",
        "-s",
        action="store_true",
        help="Run with simulated Dobots - no real hardware required. "
        "Useful for offline debugging or demoing the UI.",
    )
    parser.add_argument(
        "--simulator-arms",
        type=int,
        default=None,
        metavar="N",
        help="In simulator mode, how many fake arms to expose (default 2).",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Show each arm's port, alarm names, codes, and raw bytes, full error details, "
        "and the ports tried when no arm is found.",
    )
    parser.add_argument(
        "--create-shortcut",
        action="store_true",
        help="Create a desktop shortcut and a menu entry for the panel, then exit. "
        "On Linux with sudo, a menu entry for every user.",
    )
    return parser.parse_args(argv)


def show_panel_icon(app) -> None:
    """Show the pydobotlab icon on the windows, the taskbar, and the Linux dock."""
    from PySide6.QtGui import QIcon

    from .shortcut import ICON_PNG, SHORTCUT

    app.setWindowIcon(QIcon(str(ICON_PNG)))
    # Linux matches the windows to the .desktop file of --create-shortcut by this name.
    app.setDesktopFileName(SHORTCUT["desktop_id"])
    if sys.platform == "win32":
        import ctypes

        # Without its own id, Windows groups the panel under Python and shows Python's icon.
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(SHORTCUT["windows_app_id"])


def main(argv: list[str] | None = None) -> int:
    """Launch the GUI. Returns the Qt exit code."""
    arguments = parse_arguments(argv if argv is not None else sys.argv[1:])

    if arguments.create_shortcut:
        from .shortcut import main as create_shortcuts

        return create_shortcuts()

    if arguments.simulator:
        # Patch serial backend BEFORE any serial-touching imports happen.
        from ..simulator import install_simulator

        requested_arms = arguments.simulator_arms
        simulated_ports = install_simulator(
            arms=None if requested_arms is None else max(1, requested_arms)
        )
        print(
            f"[simulator] {len(simulated_ports)} fake arm(s): {', '.join(simulated_ports)}",
            file=sys.stderr,
        )

    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        # print, not sys.stderr.write: under pythonw.exe there is no stderr.
        print(
            "PySide6 is not installed. Install the GUI extras with:\n"
            "    pip install pydobotlab[gui]",
            file=sys.stderr,
        )
        return 2

    from ..broker import DobotBroker, is_broker_reachable
    from .hub import HubWindow

    broker = DobotBroker()
    started_here = False
    broker_error: OSError | None = None
    if not is_broker_reachable():
        try:
            broker.start()
            started_here = True
        except OSError as error:
            broker_error = error
            print(f"warning: could not start local broker: {error}", file=sys.stderr)

    from .shortcut import SHORTCUT

    app = QApplication(sys.argv[:1])  # Qt only wants progname
    app.setApplicationName(SHORTCUT["application_name"])
    show_panel_icon(app)
    if arguments.simulator:
        app.setApplicationDisplayName("pydobotlab - SIMULATOR")
    app.setOrganizationName("pydobotlab")
    app.setStyleSheet(load_stylesheet())

    # Quitting stops the broker only if this app started it, so only then
    # does the hub ask before quitting while scripts are connected.
    hub = HubWindow(developer=arguments.dev, broker=broker if started_here else None)
    if arguments.simulator:
        hub.setWindowTitle(hub.windowTitle() + "  (simulator)")
    hub.show()
    if broker_error is not None:
        from PySide6.QtWidgets import QMessageBox

        from .panel_config import PANEL_CONFIG

        message = PANEL_CONFIG["hub"]["broker_failed"]
        QMessageBox.warning(
            hub, message["title"], message["text"].format(port=broker.port, error=broker_error)
        )

    try:
        return app.exec()
    finally:
        if started_here:
            try:
                broker.stop()
            except Exception:
                pass
        if arguments.simulator:
            try:
                from ..simulator import stop_all

                stop_all()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
