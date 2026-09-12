"""Pick-and-place: lift an object from A, drop it at B.

Method names follow the DobotLab Coding Manual (3.6.x) verbatim.
"""

from __future__ import annotations

from pydobotlab import Dobot

PICKUP = (220.0, -80.0, -40.0, 0.0)  # x, y, z, r
DROP = (220.0, 80.0, -40.0, 0.0)
SAFE_Z = 30.0


def pick_one(bot: Dobot, pickup, drop) -> None:
    px, py, pz, pr = pickup
    dx, dy, dz, dr = drop

    # JUMP_XYZ (mode=0): firmware lifts to the configured jump height,
    # traverses, drops to target - perfectly safe vs. obstacles.
    bot.ptp(mode=0, x=px, y=py, z=pz, r=pr)

    bot.set_endeffector_suctioncup(enable=True, on=True)  # 3.6.13
    bot.wait(second=0.3)  # 3.6.19

    bot.ptp(mode=0, x=dx, y=dy, z=dz, r=dr)
    bot.set_endeffector_suctioncup(enable=False, on=False)
    bot.wait(second=0.2)


def main() -> None:
    # Auto-pick the first free Dobot.
    with Dobot() as bot:
        print(f"connected on {bot.port}")
        bot.clear_alarm()  # 3.6.23
        bot.set_home()  # 3.6.20
        print("homed")

        bot.motion_params = (50.0, 50.0)  # 3.6.6 (vel, acc)
        bot.jump_params = (80.0, 60.0)  # 3.6.7 (zlimit, height)

        # Park above the workspace so the first jump starts known-safe.
        bot.move_to(PICKUP[0], PICKUP[1], SAFE_Z, 0.0)

        for i in range(3):
            print(f"cycle {i + 1}: A -> B")
            pick_one(bot, PICKUP, DROP)
            print(f"cycle {i + 1}: B -> A")
            pick_one(bot, DROP, PICKUP)

        # The pick-and-place above queued many commands; block until the
        # firmware queue catches up before disconnecting.
        bot.wait_idle(timeout=120)
        bot.move_to(PICKUP[0], PICKUP[1], SAFE_Z, 0.0)
        print("done")


if __name__ == "__main__":
    main()
