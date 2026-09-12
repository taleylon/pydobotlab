"""Draw a smiley face — showcase the eager → lazy → continuous progression.

The same drawing is run THREE ways, back to back, so the speed-up and the
visual smoothness improvement are both directly comparable:

  EAGER       — one blocking ``move_to`` per segment. Each call is a
                Python<->arm round-trip plus a wait-for-completion poll.
                The arm visibly hesitates between segments and the
                wall-clock is dominated by the I/O ping-pong.

  LAZY (PTP)  — wrap the whole drawing in ``with bot.batch():``. Every
                ``ptp(MOVL_XYZ, ...)`` is appended to the firmware queue
                without running it; on block exit the firmware drains the
                whole queue as one program. No more per-segment Python
                round-trip — but the firmware still treats each MOVL
                segment as an independent trajectory that decelerates to
                zero before the next starts, so on close inspection you
                still see a tiny pause at every waypoint.

  CONTINUOUS  — same batched queue, but the actual drawing strokes use
                ``cp()`` (Continuous Path, cmd 91) instead of MOVL_XYZ.
                The firmware blends consecutive CP segments into a
                single smooth trajectory — the arm does NOT decelerate
                between waypoints. This is the right tool for drawing.

The script also **pre-validates the entire path** against a conservative
workspace envelope before sending any frame. The Magician's parallelogram
linkage forbids targets too close to the base column even when the
cylindrical radius would suggest they're reachable — the geometry below
sits comfortably outside that no-fly zone. If you change ``CENTER_X``,
``FACE_RADIUS`` etc. and your edit pushes a point out, the pre-check
prints exactly which waypoint is bad and aborts before the arm moves.

After every batched run we also call ``bot.ensure_no_alarms()``. The
firmware will occasionally silently drop CP segments it can't plan
(without raising a hard error), so the post-check ensures the script
fails loudly if the drawing didn't actually complete.

Usage:
    python examples/draw_smiley.py
    python examples/draw_smiley.py --port /dev/ttyACM0
    python examples/draw_smiley.py --skip-home          # don't re-home each run
    python examples/draw_smiley.py --skip-home --only cp
"""

from __future__ import annotations

import argparse
import math
import sys
import time

from pydobotlab import Magician, PTPMode
from pydobotlab.errors import DobotAlarmError

# ---------------------------------------------------------------------------
# Geometry — millimetres, degrees.
#
# Defaults chosen so the entire smiley sits inside the Magician's reachable
# annulus on real hardware (NOT just inside the simulator's cylindrical
# bounds — the parallelogram linkage has a "no-fly" interior even within
# the nominal radius). Closest point is (190, 0) ≈ 190 mm from the base;
# farthest is (290, 0) ≈ 290 mm. Both well clear of the limits.
# ---------------------------------------------------------------------------

CENTER_X = 240.0
CENTER_Y = 0.0
Z_DRAW = -45.0  # pen tip touches paper
Z_TRAVEL = -25.0  # pen-up height

FACE_RADIUS = 50.0  # → leftmost point of the face = (190, 0)
EYE_RADIUS = 7.0
EYE_OFFSET_X = 16.0
EYE_OFFSET_Y = 18.0
MOUTH_RADIUS = 28.0
MOUTH_HALF_DEG = 65.0

CIRCLE_SAMPLES = 64
ARC_SAMPLES = 32

# Drawing speed (mm/s). Used by cp() in the CONTINUOUS run.
DRAW_VELOCITY = 80.0


# ---------------------------------------------------------------------------
# Workspace envelope used by the pre-check. Conservative — strictly inside
# the firmware's actual envelope so we leave a small safety margin. Tweak
# WORKSPACE if your specific Magician has a different reach.
# ---------------------------------------------------------------------------

WORKSPACE = {
    # The Magician's parallelogram-arm "no-fly zone" extends quite a bit
    # further out than the nominal cylindrical inner radius — real-hardware
    # testing showed an old smiley centred at (220, 0) with R=60 (closest
    # point: 160 mm) failed mid-stroke. 180 mm is a safe lower bound on
    # standard educational kits. If your specific arm reaches closer in,
    # lower this; if it fails on the default geometry, raise it.
    "min_radius_mm": 180.0,
    "max_radius_mm": 300.0,  # outer reach on a Magician
    "z_min_mm": -80.0,
    "z_max_mm": 130.0,
}


class WorkspaceError(ValueError):
    """A waypoint is outside the conservative workspace envelope."""


def check_workspace(points: list[tuple[float, float, float]], *, workspace=WORKSPACE) -> None:
    """Raise WorkspaceError if any ``(x, y, z)`` point is out of bounds.

    Pre-validating EVERY waypoint before sending a single frame is the only
    reliable way to catch a bad smiley on real hardware: the firmware may
    silently drop unreachable CP segments instead of setting an alarm bit,
    so the queue drains "successfully" but the picture is incomplete.
    """
    bad: list[tuple[int, tuple[float, float, float], str]] = []
    for i, (x, y, z) in enumerate(points):
        r = math.hypot(x, y)
        problems = []
        if r < workspace["min_radius_mm"]:
            problems.append(
                f"too close to base column ({r:.1f} mm < {workspace['min_radius_mm']:.0f} mm)"
            )
        if r > workspace["max_radius_mm"]:
            problems.append(
                f"beyond outer reach ({r:.1f} mm > {workspace['max_radius_mm']:.0f} mm)"
            )
        if z < workspace["z_min_mm"]:
            problems.append(f"Z too low ({z:.1f} mm < {workspace['z_min_mm']:.0f} mm)")
        if z > workspace["z_max_mm"]:
            problems.append(f"Z too high ({z:.1f} mm > {workspace['z_max_mm']:.0f} mm)")
        if problems:
            bad.append((i, (x, y, z), "; ".join(problems)))
    if bad:
        msg = (
            f"{len(bad)} of {len(points)} waypoints are outside the conservative "
            f"workspace envelope:\n"
            + "\n".join(
                f"  pt #{i}  ({x:.1f}, {y:.1f}, {z:.1f})  →  {why}" for i, (x, y, z), why in bad[:5]
            )
            + ("\n  …" if len(bad) > 5 else "")
            + "\n\nAdjust CENTER_X / FACE_RADIUS so every point's radius is "
            f"between {workspace['min_radius_mm']:.0f} and "
            f"{workspace['max_radius_mm']:.0f} mm."
        )
        raise WorkspaceError(msg)


# ---------------------------------------------------------------------------
# Stroke construction.
# ---------------------------------------------------------------------------


def circle(cx: float, cy: float, r: float, n: int = CIRCLE_SAMPLES) -> list[tuple[float, float]]:
    return [
        (cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n))
        for i in range(n + 1)
    ]


def arc(
    cx: float, cy: float, r: float, start_deg: float, end_deg: float, n: int = ARC_SAMPLES
) -> list[tuple[float, float]]:
    out = []
    a0 = math.radians(start_deg)
    a1 = math.radians(end_deg)
    for i in range(n + 1):
        t = i / n
        theta = a0 + (a1 - a0) * t
        out.append((cx + r * math.cos(theta), cy + r * math.sin(theta)))
    return out


def all_strokes() -> list[list[tuple[float, float]]]:
    """All polylines that make up the smiley, in drawing order."""
    return [
        circle(CENTER_X, CENTER_Y, FACE_RADIUS),
        circle(CENTER_X + EYE_OFFSET_X, CENTER_Y + EYE_OFFSET_Y, EYE_RADIUS),
        circle(CENTER_X + EYE_OFFSET_X, CENTER_Y - EYE_OFFSET_Y, EYE_RADIUS),
        arc(
            CENTER_X,
            CENTER_Y,
            MOUTH_RADIUS,
            start_deg=-180.0 + MOUTH_HALF_DEG,
            end_deg=-MOUTH_HALF_DEG,
        ),
    ]


def all_waypoints() -> list[tuple[float, float, float]]:
    """Every (x, y, z) the arm will visit during a single drawing run.

    Used by :func:`check_workspace` to bail out before the first frame goes
    on the wire if the geometry pushes anything into the unreachable zone.
    """
    pts: list[tuple[float, float, float]] = []
    for stroke in all_strokes():
        x0, y0 = stroke[0]
        pts.append((x0, y0, Z_TRAVEL))  # approach
        pts.append((x0, y0, Z_DRAW))  # pen down
        for x, y in stroke[1:]:
            pts.append((x, y, Z_DRAW))  # along the stroke
        pts.append((x, y, Z_TRAVEL))  # pen up
    return pts


def n_segments() -> int:
    return sum(len(s) + 2 for s in all_strokes())  # +2 for pen-up + pen-down


# ---------------------------------------------------------------------------
# (1) EAGER strategy: one move at a time, blocking.
# ---------------------------------------------------------------------------


def draw_eager(bot: Magician) -> None:
    """Each segment is a blocking move_to() — slow, with visible hiccups."""
    for stroke in all_strokes():
        x0, y0 = stroke[0]
        bot.move_to(x0, y0, Z_TRAVEL, 0.0, mode=PTPMode.MOVJ_XYZ)
        bot.move_to(x0, y0, Z_DRAW, 0.0, mode=PTPMode.MOVL_XYZ)
        for x, y in stroke[1:]:
            bot.move_to(x, y, Z_DRAW, 0.0, mode=PTPMode.MOVL_XYZ)
        bot.move_to(x, y, Z_TRAVEL, 0.0, mode=PTPMode.MOVL_XYZ)


# ---------------------------------------------------------------------------
# (2) LAZY PTP strategy: stack the entire drawing, run as one queued program.
# ---------------------------------------------------------------------------


def draw_lazy(bot: Magician) -> None:
    n = n_segments()
    print(f"  [lazy] stacking ~{n} segments into the firmware queue (arm still motionless)...")
    t_stack0 = time.monotonic()

    with bot.batch():
        for stroke in all_strokes():
            x0, y0 = stroke[0]
            bot.ptp(PTPMode.MOVJ_XYZ, x0, y0, Z_TRAVEL, 0.0)
            bot.ptp(PTPMode.MOVL_XYZ, x0, y0, Z_DRAW, 0.0)
            for x, y in stroke[1:]:
                bot.ptp(PTPMode.MOVL_XYZ, x, y, Z_DRAW, 0.0)
            bot.ptp(PTPMode.MOVL_XYZ, x, y, Z_TRAVEL, 0.0)

    t_stack1 = time.monotonic()
    print(f"  [lazy] queued in {t_stack1 - t_stack0:.2f}s. Firmware draining...")
    t_run0 = time.monotonic()
    bot.wait_idle(timeout=300)
    t_run1 = time.monotonic()
    print(f"  [lazy] firmware finished drawing in {t_run1 - t_run0:.1f}s")
    print(f"  [lazy] total wall-clock: {t_run1 - t_stack0:.1f}s")


# ---------------------------------------------------------------------------
# (3) CONTINUOUS strategy: same batched queue, but drawing strokes use cp().
# ---------------------------------------------------------------------------


def draw_continuous(bot: Magician) -> None:
    n = n_segments()
    bot.set_cp_params(plan_acc=200.0, junction_vel=200.0, acc=200.0)

    print(f"  [cp] stacking ~{n} segments (cp() blends them — no per-segment pause)...")
    t_stack0 = time.monotonic()

    with bot.batch():
        for stroke in all_strokes():
            x0, y0 = stroke[0]
            bot.ptp(PTPMode.MOVJ_XYZ, x0, y0, Z_TRAVEL, 0.0)
            bot.ptp(PTPMode.MOVL_XYZ, x0, y0, Z_DRAW, 0.0)
            for x, y in stroke[1:]:
                bot.cp(x, y, Z_DRAW, velocity=DRAW_VELOCITY)
            bot.ptp(PTPMode.MOVL_XYZ, x, y, Z_TRAVEL, 0.0)

    t_stack1 = time.monotonic()
    print(f"  [cp] queued in {t_stack1 - t_stack0:.2f}s. Firmware draining...")
    t_run0 = time.monotonic()
    bot.wait_idle(timeout=300)
    t_run1 = time.monotonic()
    print(f"  [cp] firmware finished drawing in {t_run1 - t_run0:.1f}s")
    print(f"  [cp] total wall-clock: {t_run1 - t_stack0:.1f}s")


# ---------------------------------------------------------------------------
# Post-run integrity check. The firmware sometimes silently drops a CP
# segment it can't plan (no alarm raised, no error returned, the queue
# index advances anyway). Calling ensure_no_alarms() AFTER wait_idle()
# catches the obvious "the firmware aborted with an alarm bit" case. For
# the truly silent failure case our only line of defence is the pre-check.
# ---------------------------------------------------------------------------


def verify_clean(bot: Magician, run_label: str) -> bool:
    alarms = bot.get_alarms()
    if not alarms:
        return True
    print(f"  [!!] {run_label} finished WITH ACTIVE ALARMS:")
    for line in alarms.format():
        print(f"       • {line}")
    print(
        "  [!!] the drawing is INCOMPLETE — calling clear_alarm() so the next run can start clean."
    )
    try:
        bot.clear_alarm()
    except Exception:
        pass
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="pydobotlab smiley demo")
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
        help="serial port (same as positional; flag wins if both given)",
    )
    parser.add_argument(
        "--skip-home",
        action="store_true",
        help="skip the initial set_home() — useful when re-running tests "
        "back to back and the arm is already calibrated.",
    )
    parser.add_argument(
        "--only",
        choices=["eager", "lazy", "cp", "all"],
        default="all",
        help="which run to perform; default 'all' runs eager → lazy → cp.",
    )
    args = parser.parse_args()
    port = args.port_flag or args.port_positional

    # 1. Pre-check the geometry BEFORE opening the port. If the geometry is
    #    wrong, we don't even want to home — fail fast with the bad point.
    waypoints = all_waypoints()
    print(f"validating {len(waypoints)} waypoints against the workspace envelope...")
    try:
        check_workspace(waypoints)
    except WorkspaceError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 2
    print("  all waypoints reachable.")

    with Magician(port=port) as bot:
        print(f"connected on {bot.port}")
        try:
            bot.clear_alarm()
        except Exception:
            pass
        if not args.skip_home:
            print("homing...")
            bot.set_home()
        else:
            print("--skip-home given; skipping set_home()")

        # Same speed for a fair comparison across runs.
        bot.motion_params = (30.0, 30.0)

        # Track per-run success so the final message is honest.
        run_results: dict[str, bool] = {}

        if args.only in ("eager", "all"):
            print(f"\n=== EAGER: move_to() per segment ({n_segments()} segments) ===")
            t0 = time.monotonic()
            try:
                draw_eager(bot)
                run_results["eager"] = verify_clean(bot, "eager")
            except DobotAlarmError as e:
                print(f"  [!!] eager run aborted: {e}")
                run_results["eager"] = False
                try:
                    bot.clear_alarm()
                except Exception:
                    pass
            print(f"  [eager] total wall-clock: {time.monotonic() - t0:.1f}s")
            bot.move_to(CENTER_X, CENTER_Y, Z_TRAVEL, 0.0)

        if args.only in ("lazy", "all"):
            print("\n=== LAZY (PTP MOVL inside batch): one queued program ===")
            try:
                draw_lazy(bot)
                run_results["lazy"] = verify_clean(bot, "lazy")
            except DobotAlarmError as e:
                print(f"  [!!] lazy run aborted: {e}")
                run_results["lazy"] = False
                try:
                    bot.clear_alarm()
                except Exception:
                    pass
            bot.move_to(CENTER_X, CENTER_Y, Z_TRAVEL, 0.0)

        if args.only in ("cp", "all"):
            print("\n=== CONTINUOUS (cp() inside batch): blended path ===")
            try:
                draw_continuous(bot)
                run_results["cp"] = verify_clean(bot, "cp")
            except DobotAlarmError as e:
                print(f"  [!!] cp run aborted: {e}")
                run_results["cp"] = False
                try:
                    bot.clear_alarm()
                except Exception:
                    pass
            bot.move_to(CENTER_X, CENTER_Y, Z_TRAVEL, 0.0)

        # Final honest summary.
        print()
        all_ok = all(run_results.values()) if run_results else False
        if all_ok:
            print("smiley complete — all runs finished with no active alarms.")
            return 0
        failed = [name for name, ok in run_results.items() if not ok]
        print(f"smiley INCOMPLETE — runs with active alarms: {failed}")
        print(
            "  Most likely cause: a waypoint just outside the firmware's "
            "reachable zone. Try moving CENTER_X further from the base or "
            "shrinking FACE_RADIUS."
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
