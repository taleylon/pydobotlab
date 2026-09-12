"""End-to-end smoke test on real hardware.

Usage (any of these work):
    python examples/smoke_test.py                       # auto-pick
    python examples/smoke_test.py /dev/ttyUSB0          # positional
    python examples/smoke_test.py /dev/ttyACM0          # CDC ACM (common on Ubuntu)
    python examples/smoke_test.py --port /dev/ttyACM0   # flag form
    python examples/smoke_test.py -p COM3               # Windows

Method names follow DobotLab 3.6.x verbatim where applicable.
"""

from __future__ import annotations

import argparse
import sys
import time
from queue import Empty

from pydobotlab import Magician, PTPMode


def main() -> int:
    parser = argparse.ArgumentParser(description="pydobotlab smoke test")
    # Accept the port either as a positional OR as --port/-p. Whichever the
    # user gives, the other will be None; flag wins on conflict.
    parser.add_argument(
        "port_positional",
        nargs="?",
        default=None,
        metavar="PORT",
        help="serial port (omit to auto-pick; e.g. /dev/ttyUSB0, /dev/ttyACM0, COM3)",
    )
    parser.add_argument(
        "-p",
        "--port",
        dest="port_flag",
        default=None,
        metavar="PORT",
        help="serial port (same as positional; takes precedence if both given)",
    )
    parser.add_argument("--skip-home", action="store_true")
    args = parser.parse_args()
    port = args.port_flag or args.port_positional  # flag wins

    with Magician(port=port) as bot:
        print(f"connected on {bot.port}")

        # 1. Alarms (3.6.23)
        alarms = bot.get_alarms()
        if alarms:
            print(f"alarms active: {alarms.names()}; clearing...")
            bot.clear_alarm()
            assert not bot.get_alarms(), "alarms still set after clear"
        else:
            print("no alarms")

        # 2. Device info
        print(f"firmware version: {bot.get_device_version()}")

        # 3. Pose (3.6.21) — GitBook tuple unpack
        x, y, z, r, joints = bot.get_pose()
        print(
            f"current pose: x={x:.1f} y={y:.1f} z={z:.1f} r={r:.1f}  "
            f"joints={[round(j, 1) for j in joints]}"
        )

        # 4. HOME (3.6.20)
        if not args.skip_home:
            print("homing...")
            t0 = time.monotonic()
            bot.set_home()
            print(f"home done in {time.monotonic() - t0:.1f}s")

        # 5. Movement rate (3.6.6) — property style
        bot.motion_params = (50.0, 50.0)
        bot.move_to(200, 0, 50, 0, mode=PTPMode.MOVJ_XYZ)
        print("moved to (200, 0, 50, 0)")

        # 6. Stack-then-execute (lazy run)
        path = [(200, -50, 0, 0), (200, 50, 0, 0), (250, 0, 0, 0), (200, 0, 50, 0)]
        print(f"queueing batch of {len(path)} moves...")
        with bot.batch():
            for x, y, z, r in path:
                bot.ptp(PTPMode.MOVL_XYZ, x, y, z, r)
        bot.wait_idle(timeout=30)
        print("batch complete")

        # 7. Pose stream (pydobotlab addition; not in DobotLab)
        print("starting pose stream @ 20 Hz for 1 second...")
        q = bot.start_pose_stream(hz=20)
        time.sleep(1.0)
        bot.stop_pose_stream()
        n = 0
        while True:
            try:
                _ = q.get_nowait()
                n += 1
            except Empty:
                break
        print(f"received {n} pose samples")

        # 8. End effector (3.6.13)
        print("toggling suction cup")
        bot.set_endeffector_suctioncup(enable=True, on=True)
        time.sleep(0.3)
        bot.set_endeffector_suctioncup(enable=False, on=False)

        print("smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
