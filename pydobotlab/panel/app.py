"""Entry point for the pydobotlab control-panel GUI.

Enables the option to run it through the ``pydobotlab-panel`` console script after installing
``pip install pydobotlab[gui]``, or with ``python -m pydobotlab.panel``.

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
        help="Show each arm's port, alarm names, codes, and raw bytes, and full error details.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Launch the GUI. Returns the Qt exit code."""
    arguments = parse_arguments(argv if argv is not None else sys.argv[1:])

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
        sys.stderr.write(
            "PySide6 is not installed. Install the GUI extras with:\n"
            "    pip install pydobotlab[gui]\n"
        )
        return 2

    from ..broker import DobotBroker, is_broker_reachable
    from .hub import HubWindow

    broker = DobotBroker()
    started_here = False
    if not is_broker_reachable():
        try:
            broker.start()
            started_here = True
        except OSError as error:
            sys.stderr.write(f"warning: could not start local broker: {error}\n")

    app = QApplication(sys.argv[:1])  # Qt only wants progname
    app.setApplicationName("pydobotlab")
    if arguments.simulator:
        app.setApplicationDisplayName("pydobotlab - SIMULATOR")
    app.setOrganizationName("pydobotlab")
    app.setStyleSheet(load_stylesheet())

    hub = HubWindow(developer=arguments.dev)
    if arguments.simulator:
        hub.setWindowTitle(hub.windowTitle() + "  (simulator)")
    hub.show()

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
