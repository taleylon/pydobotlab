"""Multi-arm patterns: each Dobot is its own independent object.

There is no batch / group abstraction. Each ``Dobot`` instance owns one
serial connection, one lock, one queue index, one set of background
threads. Choreography between arms is the application's job.
"""

from __future__ import annotations

import threading

from pydobotlab import (
    Discovery,
    Dobot,
    DobotConnectionError,
    DobotPortInUseError,
    PTPMode,
)

# 1. What's plugged in?
print("Serial ports the OS sees:")
for info in Discovery.list_ports():
    flag = "(known Dobot adapter)" if info.is_known_dobot_adapter else ""
    busy = "[claimed by us]" if info.is_claimed else ""
    print(f"  {info.port:<20} {info.description!r} {flag} {busy}")

# 2. Which of those answer like a Dobot?
print("\nProbing for live Dobots...")
for hit in Discovery.discover():
    print(f"  {hit.port}  serial={hit.serial_number}")

# 3a. Auto-pick (constructor default).
with Dobot() as bot:
    x, y, z, r, joints = bot.get_pose()  # GitBook tuple shape
    print(f"\nauto-picked {bot.port}, pose=({x:.1f}, {y:.1f}, {z:.1f}, {r:.1f}); joints={joints}")

# 3b. Explicit port — auto-pick is bypassed.
try:
    with Dobot("/dev/ttyUSB0") as bot:
        print(f"explicit /dev/ttyUSB0, pose = {tuple(bot.get_pose())}")
except DobotPortInUseError:
    print("/dev/ttyUSB0 is busy")
except DobotConnectionError as e:
    print(f"/dev/ttyUSB0 unreachable: {e}")

# 4. Drive two arms concurrently. Two independent Dobot()s land on
#    different physical ports thanks to auto-pick at connect() time.
left = Dobot()
right = Dobot()


def per_arm(arm: Dobot, label: str) -> None:
    with arm:
        print(f"[{label}] connected on {arm.port}")
        arm.clear_alarm()
        arm.set_home()
        arm.motion_params = (50.0, 50.0)
        with arm.batch():
            for x, y in [(200, -50), (200, 50), (250, 0)]:
                arm.ptp(PTPMode.MOVL_XYZ, x, y, 0, 0)
        arm.wait_idle(timeout=30)
        print(f"[{label}] done")


threads = [
    threading.Thread(target=per_arm, args=(left, "left"), name="left"),
    threading.Thread(target=per_arm, args=(right, "right"), name="right"),
]
for t in threads:
    t.start()
for t in threads:
    t.join()
print("all arms finished")
