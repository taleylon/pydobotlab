"""Drive two (or more) Dobots from a Python script while their control
panels are open and showing live state.

Workflow:

    1.  Plug in two Dobot Magicians (USB).
    2.  In one terminal:    pydobotlab-panel
        - In the hub, click "Open Control Panel" twice - once per arm.
        - Each panel shows a live X / Y / Z / R + J1..J4 readout updating
          at ~30 Hz, and the speed slider, jog pads, end-effector tabs and
          Set Home / Clear Alarm buttons all work.
    3.  In another terminal (or PyCharm):
            python examples/two_dobots_with_panels.py
        - The script's `Dobot()` calls AUTO-DETECT the running panel's
          broker on 127.0.0.1:8765 and route through it. No port arg, no
          fuss - it just works because the broker arbitrates traffic.

What you should see while the script runs:

    * Both panels' coordinate readouts update in real time as the arms
      move under script control.
    * If you grab one of the panel's jog pads mid-script, your jog
      commands interleave with the script's commands at the broker's
      per-port lock - neither corrupts the other on the wire.
    * If you push an unlocked arm by hand, the panel reflects the new
      pose even though the script issued no command.

If the panel isn't running, this script still works - `Dobot()` falls
back to opening the serial port directly. You just won't get the live
visualisation.
"""

from __future__ import annotations

import threading

from pydobotlab import Dobot, PTPMode

# Two corners-of-a-square tours, slightly offset between arms so a single
# observer can tell which panel updates correspond to which arm.
TOURS = [
    [(220, -60, 0, 0), (260, -60, 0, 0), (260, 60, 0, 0), (220, 60, 0, 0)],
    [(220, 60, 0, 0), (260, 60, 0, 0), (260, -60, 0, 0), (220, -60, 0, 0)],
]


def per_arm(
    arm: Dobot, label: str, tour: list[tuple[float, float, float, float]], laps: int = 4
) -> None:
    """One arm's program: home, set speed, walk a square `laps` times."""
    with arm:
        print(f"[{label}] connected on {arm.port}")
        arm.clear_alarm()
        arm.set_home()
        arm.motion_params = (40.0, 40.0)  # vel, acc - both sides

        for lap in range(laps):
            print(f"[{label}] lap {lap + 1}/{laps}")
            with arm.batch():
                # Queue the whole lap; firmware runs it as one continuous
                # program. The panel keeps polling get_pose() at 30 Hz,
                # going through the same broker lock - readouts stay live.
                for x, y, z, r in tour:
                    arm.ptp(PTPMode.MOVL_XYZ, x, y, z, r)
            arm.wait_idle(timeout=60)

        # Park up at the start of the tour.
        x0, y0, z0, r0 = tour[0]
        arm.move_to(x0, y0, 50.0, r0)
        print(f"[{label}] done")


def main() -> None:
    # Two independent Dobot objects. Each one auto-picks a free arm when
    # connect() runs (auto-pick respects the broker's port list when the
    # panel is up; falls back to direct serial scan otherwise).
    bots = [Dobot() for _ in range(2)]

    threads = [
        threading.Thread(
            target=per_arm,
            args=(bots[i], f"arm-{i + 1}", TOURS[i]),
            name=f"arm-{i + 1}",
        )
        for i in range(2)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print("all arms finished")


if __name__ == "__main__":
    main()
