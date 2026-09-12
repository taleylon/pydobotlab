"""Demonstrate the unreachable-target error path - works against simulator.

Run with the simulator (no hardware needed):
    python examples/unreachable_target.py --simulator

Or against a real arm:
    python examples/unreachable_target.py
"""

from __future__ import annotations

import argparse
import sys

from pydobotlab import Dobot, DobotKinematicError, PTPMode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--simulator",
        action="store_true",
        help="Run against the in-process simulator (no hardware needed).",
    )
    args = parser.parse_args()

    if args.simulator:
        from pydobotlab.simulator import install_simulator

        install_simulator(arms=1)

    with Dobot(via_broker=False) as bot:
        bot.clear_alarm()
        bot.set_home()

        # 1. Reachable: this works.
        print("Moving to (220, 0, 50)... ", end="", flush=True)
        bot.move_to(220, 0, 50, 0, mode=PTPMode.MOVJ_XYZ)
        print("OK")

        # 2. Unreachable: way outside the workspace.
        print("Moving to (500, 500, 0)... ", end="", flush=True)
        try:
            bot.move_to(500, 500, 0, 0, mode=PTPMode.MOVL_XYZ, timeout=5)
        except DobotKinematicError as e:
            print(f"REJECTED - {type(e).__name__}: {e}")
            print(f"    active alarms: {e.alarms}")
        else:
            print("(unexpectedly succeeded - workspace bounds not enforced)")
            return 1

        # 3. Recovery: clear the alarm, then continue.
        print("\nCalling clear_alarm() to recover...")
        bot.clear_alarm()
        assert not bot.get_alarms(), "alarms should be cleared"

        print("Moving to a reachable point (260, -50, 30)... ", end="", flush=True)
        bot.move_to(260, -50, 30, 0, mode=PTPMode.MOVJ_XYZ)
        print("OK")

    print("\nDone - student can catch DobotKinematicError, call clear_alarm, retry.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
