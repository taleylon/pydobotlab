"""Entry point for the pydobotlab control-panel GUI.

Exposed as the ``pydobotlab-panel`` console script (added by
``pip install pydobotlab[gui]``) and as ``python -m pydobotlab.panel``.

Simulator mode
--------------

    pydobotlab-panel --simulator                  # 2 fake arms, no hardware needed
    pydobotlab-panel --simulator --simulator-arms 4

Useful for inspecting / debugging the panel UI when no real Dobot is
connected, or for writing tutorials offline. The simulator monkey-patches
the serial backend; everything else (broker, hub, control panel, jog,
home, pose stream, end-effector tabs) runs unmodified against fake arms
that interpolate motion at ~30 Hz so the pose readout actually animates.
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
        help="Run with simulated Dobots — no real hardware required. "
        "Useful for offline debugging or demoing the UI.",
    )
    parser.add_argument(
        "--simulator-arms",
        type=int,
        default=2,
        metavar="N",
        help="In simulator mode, how many fake arms to expose (default 2).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Launch the GUI. Returns the Qt exit code."""
    arguments = parse_arguments(argv if argv is not None else sys.argv[1:])

    if arguments.simulator:
        # Patch serial backend BEFORE any serial-touching imports happen.
        from ..simulator import install_simulator

        simulated_ports = install_simulator(arms=max(1, arguments.simulator_arms))
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
        app.setApplicationDisplayName("pydobotlab — SIMULATOR")
    app.setOrganizationName("pydobotlab")
    app.setStyleSheet(load_stylesheet())

    hub = HubWindow()
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
