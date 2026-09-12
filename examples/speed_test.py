"""Verify that the speed setting actually controls how fast the arm moves.

Runs the same fixed-distance move twice — once at 100 % speed, once at 25 %
— and prints the wall-clock for each. On a working setup the slow run takes
~4× longer than the fast one (within friction / acceleration overhead).

Use it on real hardware to confirm the speed slider in pydobotlab-panel is
plumbed through correctly. Use it with --simulator for offline debugging
or in CI.

Usage:
    python examples/speed_test.py                    # real arm, auto-pick
    python examples/speed_test.py --simulator        # no hardware needed
"""

from __future__ import annotations

import argparse
import sys
import time

from pydobotlab import Dobot, PTPMode


def time_move(bot: Dobot, x: float, y: float, z: float, r: float = 0.0) -> float:
    t0 = time.monotonic()
    bot.move_to(x, y, z, r, mode=PTPMode.MOVL_XYZ, timeout=30)
    return time.monotonic() - t0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulator", action="store_true")
    args = parser.parse_args()

    if args.simulator:
        from pydobotlab.simulator import install_simulator

        install_simulator(arms=1)

    with Dobot(via_broker=False) as bot:
        bot.clear_alarm()
        bot.set_home()

        # Park at a known starting point so the timings are comparable.
        bot.move_to(220, -60, 0, 0)

        # 100 % speed
        bot.motion_params = (100.0, 100.0)
        bot.set_jog_common_params(100.0, 100.0)
        t_fast = time_move(bot, 220, +60, 0, 0)
        print(f"100% speed: {t_fast:.2f}s")

        # Reset the start position
        bot.move_to(220, -60, 0, 0)

        # 25 % speed
        bot.motion_params = (25.0, 25.0)
        bot.set_jog_common_params(25.0, 25.0)
        t_slow = time_move(bot, 220, +60, 0, 0)
        print(f" 25% speed: {t_slow:.2f}s")

        ratio = t_slow / max(t_fast, 1e-9)
        print(f"\nslow / fast = {ratio:.2f}× (expect roughly 4×)")
        if ratio < 2.5:
            print(
                "WARNING: the speed setting doesn't seem to be honoured by "
                "the arm. Check that motion_params is being sent before "
                "the move and that the firmware accepts the value."
            )
            return 1
        print("OK — the speed setting controls the move duration as expected.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
