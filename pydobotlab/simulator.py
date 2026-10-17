"""Simulator backend - view & test the panel without a real Dobot.

Activate with::

    pydobotlab-panel --simulator

or programmatically::

    from pydobotlab.simulator import install_simulator
    install_simulator(arms=2)
    # now any Dobot()/Discovery.discover()/pydobotlab-panel will see fake arms

What it does
------------

* Installs a fake :class:`pyserial.Serial` substitute that, instead of
  driving real bytes over USB, parses each Dobot frame in software and
  returns a synthetic response from a virtual arm.
* Monkey-patches ``serial.tools.list_ports.comports()`` so the discovery
  layer sees N fake ports (``/dev/sim0``, ``/dev/sim1``, ...).
* Each fake arm has its own pose (initially home) and a command queue that
  runs in order in a daemon thread: moves interpolate so the panel's pose
  readout animates, other commands take effect when they reach the head.
  Like the real arm, the queue does not run while an alarm is active.

It's intentionally additive: nothing in the rest of the library knows
the simulator exists. Without ``--simulator`` (or ``install_simulator()``
in code), behaviour is exactly as before.
"""

from __future__ import annotations

import math
import struct
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from .commands import CommandID
from .config import get_config
from .protocol import (
    CTRL_QUEUED,
    CTRL_RW,
    pack_floats,
)
from .protocol import (
    pack as pack,
)
from .protocol import (
    unpack as unpack,
)

# Alarm bit set when a target is outside the workspace: PLAN_INVERSE_CALCULATION
# (0x11), the code the real arm reports for an unreachable target, so students
# can test their error handling without hardware.
ALARM_OUT_OF_WORKSPACE_CODE = 0x11


# ---------------------------------------------------------------------------
# Workspace of the real arm
#
# Geometry and joint ranges of the Dobot Magician from its user guide (V2.3.1):
# arm lengths from Figure 2.9, joint ranges and maximum reach from Table 2.2.
# They are physical properties of the arm, so they are constants, not settings.
# ---------------------------------------------------------------------------

REAR_ARM_LENGTH_MM = 135.0
FOREARM_LENGTH_MM = 147.0
BASE_RANGE_DEG = (-90.0, 90.0)
REAR_ARM_RANGE_DEG = (0.0, 85.0)  # from vertical, positive leaning forward
FOREARM_RANGE_DEG = (-10.0, 90.0)  # from horizontal, positive pointing down
MAXIMUM_REACH_MM = 320.0

# Coordinates are those of the tool point, which the firmware places a
# tool-specific distance in front of the wrist (EndEffectorParams). The guide
# does not give that distance, so it is chosen to make the farthest reachable
# point the official maximum reach.
TOOL_OFFSET_MM = MAXIMUM_REACH_MM - (
    REAR_ARM_LENGTH_MM * math.sin(math.radians(REAR_ARM_RANGE_DEG[1])) + FOREARM_LENGTH_MM
)

ANGLE_TOLERANCE_DEG = 1e-6


def is_within(angle: float, angle_range: tuple[float, float]) -> bool:
    low, high = angle_range
    return low - ANGLE_TOLERANCE_DEG <= angle <= high + ANGLE_TOLERANCE_DEG


def joint_angles(x: float, y: float, z: float) -> tuple[float, float, float] | None:
    """Base, rear-arm, and forearm angles in degrees that put the tool at ``(x, y, z)``.

    ``None`` if no angles within the joint ranges reach the point. The origin is
    the center of the three motors, as on the real arm.
    """
    base = math.degrees(math.atan2(y, x))
    if not is_within(base, BASE_RANGE_DEG):
        return None
    wrist_radius = math.hypot(x, y) - TOOL_OFFSET_MM
    wrist_distance = math.hypot(wrist_radius, z)
    if wrist_distance == 0:
        return None
    # Law of cosines: angle between the rear arm and the line to the wrist.
    cosine = (REAR_ARM_LENGTH_MM**2 + wrist_distance**2 - FOREARM_LENGTH_MM**2) / (
        2 * REAR_ARM_LENGTH_MM * wrist_distance
    )
    if not -1.0 <= cosine <= 1.0:
        return None
    wrist_direction = math.degrees(math.atan2(wrist_radius, z))  # from vertical
    elbow_angle = math.degrees(math.acos(cosine))
    for rear_arm in (wrist_direction - elbow_angle, wrist_direction + elbow_angle):
        elbow_radius = REAR_ARM_LENGTH_MM * math.sin(math.radians(rear_arm))
        elbow_height = REAR_ARM_LENGTH_MM * math.cos(math.radians(rear_arm))
        forearm = math.degrees(math.atan2(elbow_height - z, wrist_radius - elbow_radius))
        if is_within(rear_arm, REAR_ARM_RANGE_DEG) and is_within(forearm, FOREARM_RANGE_DEG):
            return base, rear_arm, forearm
    return None


def is_reachable(x: float, y: float, z: float) -> bool:
    """Whether the real arm can move its tool to ``(x, y, z)``."""
    return joint_angles(x, y, z) is not None


# ---------------------------------------------------------------------------
# FakeDobot - software-only Dobot Magician
# ---------------------------------------------------------------------------


@dataclass
class ArmState:
    # Cartesian + joint, all snake-cased to mirror Pose
    x: float = 200.0
    y: float = 0.0
    z: float = 50.0
    r: float = 0.0
    j1: float = 0.0
    j2: float = 0.0
    j3: float = 0.0
    j4: float = 0.0


@dataclass
class MotionTarget:
    x: float = 200.0
    y: float = 0.0
    z: float = 50.0
    r: float = 0.0


@dataclass
class QueuedCommand:
    """A command waiting in, or running at the head of, the simulated queue."""

    queue_index: int
    # Runs when the command reaches the head of the queue and returns the
    # waypoints of the move it starts (none for commands that do not move).
    start: Callable[[], list[MotionTarget]]
    wait_seconds: float = 0.0
    waypoints: list[MotionTarget] | None = None  # None until the command starts
    runs_during_alarm: bool = False  # homing runs also while an alarm is active


@dataclass
class ActiveJog:
    """An ongoing JOG: nudge the pose in this direction every sim tick."""

    mode: int  # 0 = COORDINATE, 1 = JOINT
    cmd: int  # 1..8 - see protocol.JOGCmd


class FakeDobot:
    """A self-contained virtual Dobot Magician.

    One instance per simulated port. Owns a small motion model that
    interpolates toward the latest target at ``speed_mm_per_s`` so that
    pose readouts animate visibly while a script runs.
    """

    def __init__(
        self,
        port: str = "/dev/sim0",
        *,
        speed_mm_per_s: float | None = None,
        tick_hz: float | None = None,
        serial_number: str = "SIM-MAGICIAN",
    ) -> None:
        settings = get_config()["simulator"]
        speed_mm_per_s = settings["speed_mm_per_s"] if speed_mm_per_s is None else speed_mm_per_s
        tick_hz = settings["tick_hz"] if tick_hz is None else tick_hz
        self.port = port
        self.serial_number = serial_number
        self._state = ArmState()
        self._queue: deque[QueuedCommand] = deque()
        self._queue_running = True  # SET_QUEUED_CMD_START_EXEC / STOP_EXEC
        # While set, the sim_loop nudges the pose in this direction every
        # tick and the queue waits. set_jog_cmd(IDLE) clears it.
        self._jog: ActiveJog | None = None
        # Internal "100% velocity" baselines. Effective speed every tick is
        # baseline * (vel_ratio / 100), so the panel's speed slider directly
        # controls how fast jogs and PTPs run - same as a real arm.
        self._jog_baseline_mm = settings["jog_speed_mm_per_s"]
        self._jog_baseline_deg = settings["jog_speed_deg_per_s"]
        self._ptp_baseline_mm = float(speed_mm_per_s)
        # Velocity ratios (0..100, percent). Default 50 matches the panel
        # slider's startup value.
        self._ptp_vel_ratio: float = 50.0
        self._ptp_acc_ratio: float = 50.0
        self._jog_vel_ratio: float = 50.0
        self._jog_acc_ratio: float = 50.0
        # Recompute derived effective speeds from the defaults above.
        self._jog_speed_mm = self._jog_baseline_mm * self._jog_vel_ratio / 100.0
        self._jog_speed_deg = self._jog_baseline_deg * self._jog_vel_ratio / 100.0
        self._speed = self._ptp_baseline_mm * self._ptp_vel_ratio / 100.0
        self._jump_height = 20.0
        self._jump_zlimit = 100.0
        self._queue_added = 0
        self._queue_executed = 0
        self._alarms = bytearray(16)
        self._color_sensor = (200, 100, 50)  # arbitrary RGB
        self._lock = threading.Lock()
        # _speed is computed above from baseline * vel_ratio.
        self._tick_seconds = 1.0 / max(1.0, float(tick_hz))
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run_motion_loop, daemon=True, name=f"FakeDobot@{port}"
        )
        self._thread.start()

    # ---- background motion -------------------------------------------------

    def _run_motion_loop(self) -> None:
        while not self._stop.is_set():
            with self._lock:
                if self._jog is not None:
                    self._apply_jog_step(self._jog)
                else:
                    self.run_queue_tick()
            self._stop.wait(self._tick_seconds)

    # -- queue ---------------------------------------------------------------

    def can_run_queue(self) -> bool:
        """Whether the head of the queue may run now. Call with the lock held."""
        return (
            bool(self._queue)
            and self._queue_running
            and self._jog is None
            and (not any(self._alarms) or self._queue[0].runs_during_alarm)
        )

    def advance_queue(self) -> None:
        """Start queued commands in order and retire the finished ones.

        Commands that do not move finish at once; a move or a wait stays at
        the head until run_queue_tick completes it. Call with the lock held.
        """
        while self.can_run_queue():
            command = self._queue[0]
            if command.waypoints is None:
                command.waypoints = command.start()
            if command.waypoints or command.wait_seconds > 0:
                return
            self._queue_executed = command.queue_index
            self._queue.popleft()

    def run_queue_tick(self) -> None:
        """Advance the command at the head of the queue by one tick."""
        self.advance_queue()
        if not self.can_run_queue():
            return
        command = self._queue[0]
        if command.waypoints:
            if self.step_toward(command.waypoints[0]):
                command.waypoints.pop(0)
        else:
            command.wait_seconds -= self._tick_seconds
        self.advance_queue()

    def enqueue(
        self,
        start: Callable[[], list[MotionTarget]],
        wait_seconds: float = 0.0,
        *,
        runs_during_alarm: bool = False,
    ) -> int:
        """Add a command to the queue and return its queue index."""
        with self._lock:
            self._queue_added += 1
            self._queue.append(
                QueuedCommand(
                    self._queue_added, start, wait_seconds, runs_during_alarm=runs_during_alarm
                )
            )
            self.advance_queue()
            return self._queue_added

    def enqueue_action(self, action: Callable[[], None]) -> int:
        """Queue a command that takes effect when it reaches the head of the queue."""

        def start() -> list[MotionTarget]:
            action()
            return []

        return self.enqueue(start)

    # -- jog helpers ---------------------------------------------------------

    # JOGCmd values  -> (axis_index, sign)  inside coordinate mode.
    # axis_index 0=x, 1=y, 2=z, 3=r
    _JOG_TO_COORD = {
        1: (0, +1),
        2: (0, -1),  # AP/AN -> X+/X-
        3: (1, +1),
        4: (1, -1),  # BP/BN -> Y+/Y-
        5: (2, +1),
        6: (2, -1),  # CP/CN -> Z+/Z-
        7: (3, +1),
        8: (3, -1),  # DP/DN -> R+/R-
    }
    # Same shape, but joint mode targets j1..j4 directly.
    _JOG_TO_JOINT = {
        1: (0, +1),
        2: (0, -1),  # J1
        3: (1, +1),
        4: (1, -1),  # J2
        5: (2, +1),
        6: (2, -1),  # J3
        7: (3, +1),
        8: (3, -1),  # J4
    }
    _COORD_FIELDS = ("x", "y", "z", "r")
    _JOINT_FIELDS = ("j1", "j2", "j3", "j4")

    def _apply_jog_step(self, jog: ActiveJog) -> None:
        state = self._state
        if jog.mode == 0:
            mapping = self._JOG_TO_COORD
            fields = self._COORD_FIELDS
            # mm/s for X/Y/Z; degrees/s for R.
            speeds = (
                self._jog_speed_mm,
                self._jog_speed_mm,
                self._jog_speed_mm,
                self._jog_speed_deg,
            )
        else:
            mapping = self._JOG_TO_JOINT
            fields = self._JOINT_FIELDS
            speeds = (self._jog_speed_deg,) * 4
        axis_direction = mapping.get(jog.cmd)
        if axis_direction is None:
            return
        axis_index, sign = axis_direction
        current_value = getattr(state, fields[axis_index])
        setattr(
            state,
            fields[axis_index],
            current_value + sign * speeds[axis_index] * self._tick_seconds,
        )

    def step_toward(self, target: MotionTarget) -> bool:
        """Move one tick toward ``target``; return whether it was reached."""
        state = self._state
        dx, dy, dz = target.x - state.x, target.y - state.y, target.z - state.z
        distance = max((dx * dx + dy * dy + dz * dz) ** 0.5, 1e-9)
        step = self._speed * self._tick_seconds
        if distance <= step:
            state.x, state.y, state.z, state.r = target.x, target.y, target.z, target.r
            return True
        state.x += dx * (step / distance)
        state.y += dy * (step / distance)
        state.z += dz * (step / distance)
        # R rotates fast - interpolate proportionally to XY/Z progress.
        state.r += (target.r - state.r) * (step / distance)
        return False

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=1.0)

    # ---- helpers used by the frame handler --------------------------------

    def enqueue_home(self) -> int:
        """Queue multi-stage homing - lift Z, rotate to home XY, descend.

        Mimics the visible behaviour of a real Magician: it first lifts
        out of the work area, then swings the base around to align with
        the home position, then drops down to the home Z.
        """

        def start() -> list[MotionTarget]:
            state = self._state
            home_x, home_y, home_z, home_r = 200.0, 0.0, 50.0, 0.0
            lift_z = max(state.z, home_z) + 60.0  # safe altitude above both poses
            return [
                MotionTarget(x=state.x, y=state.y, z=lift_z, r=state.r),
                MotionTarget(x=home_x, y=home_y, z=lift_z, r=home_r),
                MotionTarget(x=home_x, y=home_y, z=home_z, r=home_r),
            ]

        return self.enqueue(start, runs_during_alarm=True)  # as the real arm does

    def set_motion_target(self, x: float, y: float, z: float, r: float) -> int:
        """Queue a point-to-point move to ``(x, y, z, r)``."""

        def start() -> list[MotionTarget]:
            if is_reachable(x, y, z):
                return [MotionTarget(x=x, y=y, z=z, r=r)]
            # The command finishes without moving and sets the workspace
            # alarm, which stops the queue until the alarm is cleared.
            self._alarms[ALARM_OUT_OF_WORKSPACE_CODE // 8] |= 1 << (ALARM_OUT_OF_WORKSPACE_CODE % 8)
            return []

        return self.enqueue(start)

    # ---- frame dispatch ----------------------------------------------------

    def handle_frame(self, frame_bytes: bytes) -> bytes:
        """Decode one Dobot frame, return the wire bytes of the response."""
        try:
            frame = unpack(frame_bytes)
        except Exception:
            return b""

        command_id = frame.cmd_id
        is_write = bool(frame.ctrl & CTRL_RW)
        is_queued = bool(frame.ctrl & CTRL_QUEUED)
        params = frame.params

        # --- Pose ----------------------------------------------------------
        if command_id == CommandID.GET_POSE:
            with self._lock:
                state = self._state
                payload = pack_floats(
                    state.x, state.y, state.z, state.r, state.j1, state.j2, state.j3, state.j4
                )
            return pack(command_id, frame.ctrl, payload)

        if command_id == CommandID.GET_POSE_L:
            return pack(command_id, frame.ctrl, pack_floats(0.0))

        # --- Alarms --------------------------------------------------------
        if command_id == CommandID.GET_ALARMS_STATE and not is_write:
            with self._lock:
                return pack(command_id, frame.ctrl, bytes(self._alarms))
        if command_id == CommandID.CLEAR_ALL_ALARMS_STATE and is_write:
            with self._lock:
                self._alarms = bytearray(16)
                self.advance_queue()
            return pack(command_id, frame.ctrl, b"")

        # --- HOME ----------------------------------------------------------
        if command_id == CommandID.SET_HOME_CMD:
            queue_index = self.enqueue_home()
            return pack(command_id, frame.ctrl, struct.pack("<Q", queue_index))

        # --- PTP -----------------------------------------------------------
        if command_id == CommandID.SET_PTP_CMD and is_write and len(params) >= 17:
            # PTP mode is accepted but the simulator models Cartesian targets only.
            x, y, z, r = struct.unpack("<4f", params[1:17])
            queue_index = self.set_motion_target(x, y, z, r)
            return pack(command_id, frame.ctrl, struct.pack("<Q", queue_index))

        # --- JOG -----------------------------------------------------------
        if command_id == CommandID.SET_JOG_CMD and is_write and len(params) >= 2:
            mode, cmd = params[0], params[1]
            with self._lock:
                if cmd == 0:  # IDLE - release jog
                    self._jog = None
                else:
                    self._jog = ActiveJog(mode=int(mode), cmd=int(cmd))
            return pack(command_id, frame.ctrl, b"")

        # --- Movement-rate / jog-rate (controlled by the panel speed slider)
        # Each one stores a (vel_ratio, acc_ratio) pair as a percentage that
        # scales the effective motion speed used by _run_motion_loop.
        if command_id == CommandID.GET_SET_PTP_COMMON_PARAMS:
            if is_write and len(params) >= 8:
                velocity, acceleration = struct.unpack("<2f", params[:8])

                def set_ptp_speed() -> None:
                    self._ptp_vel_ratio = max(0.0, min(100.0, float(velocity)))
                    self._ptp_acc_ratio = max(0.0, min(100.0, float(acceleration)))
                    self._speed = self._ptp_baseline_mm * self._ptp_vel_ratio / 100.0

                return self.apply_write(command_id, frame.ctrl, is_queued, set_ptp_speed)
            else:
                with self._lock:
                    return pack(
                        command_id,
                        frame.ctrl,
                        struct.pack("<2f", self._ptp_vel_ratio, self._ptp_acc_ratio),
                    )

        # --- Jump-mode params (zlimit, height in wire-order height/zlimit)
        if command_id == CommandID.GET_SET_PTP_JUMP_PARAMS:
            if is_write and len(params) >= 8:
                # Wire order: (jumpHeight, zLimit) - the device.py property
                # already swaps for us before sending.
                height, zlimit = struct.unpack("<2f", params[:8])

                def set_jump_params() -> None:
                    self._jump_height = float(height)
                    self._jump_zlimit = float(zlimit)

                return self.apply_write(command_id, frame.ctrl, is_queued, set_jump_params)
            else:
                with self._lock:
                    return pack(
                        command_id,
                        frame.ctrl,
                        struct.pack("<2f", self._jump_height, self._jump_zlimit),
                    )

        if command_id == CommandID.GET_SET_JOG_COMMON_PARAMS:
            if is_write and len(params) >= 8:
                velocity, acceleration = struct.unpack("<2f", params[:8])

                def set_jog_speed() -> None:
                    self._jog_vel_ratio = max(0.0, min(100.0, float(velocity)))
                    self._jog_acc_ratio = max(0.0, min(100.0, float(acceleration)))
                    self._jog_speed_mm = self._jog_baseline_mm * self._jog_vel_ratio / 100.0
                    self._jog_speed_deg = self._jog_baseline_deg * self._jog_vel_ratio / 100.0

                return self.apply_write(command_id, frame.ctrl, is_queued, set_jog_speed)
            else:
                with self._lock:
                    return pack(
                        command_id,
                        frame.ctrl,
                        struct.pack("<2f", self._jog_vel_ratio, self._jog_acc_ratio),
                    )

        # --- Wait ----------------------------------------------------------
        if command_id == CommandID.SET_WAIT_CMD and is_queued:
            (milliseconds,) = struct.unpack("<I", params[:4].ljust(4, b"\x00"))
            queue_index = self.enqueue(lambda: [], wait_seconds=milliseconds / 1000.0)
            return pack(command_id, frame.ctrl, struct.pack("<Q", queue_index))

        # --- Queue control --------------------------------------------------
        if command_id == CommandID.GET_QUEUED_CMD_CURRENT_INDEX:
            with self._lock:
                queue_index = self._queue_executed
            return pack(command_id, frame.ctrl, struct.pack("<Q", queue_index))
        if command_id == CommandID.GET_QUEUED_CMD_LEFT_SPACE:
            return pack(command_id, frame.ctrl, struct.pack("<I", 32))
        if command_id in (
            CommandID.SET_QUEUED_CMD_START_EXEC,
            CommandID.SET_QUEUED_CMD_STOP_EXEC,
            CommandID.SET_QUEUED_CMD_FORCE_STOP_EXEC,
            CommandID.SET_QUEUED_CMD_CLEAR,
        ):
            with self._lock:
                if command_id == CommandID.SET_QUEUED_CMD_START_EXEC:
                    self._queue_running = True
                    self.advance_queue()
                elif command_id == CommandID.SET_QUEUED_CMD_STOP_EXEC:
                    self._queue_running = False
                elif command_id == CommandID.SET_QUEUED_CMD_FORCE_STOP_EXEC:
                    self._queue_running = False
                    if self._queue and self._queue[0].waypoints is not None:
                        self._queue.popleft()  # abandon the command in progress
                else:
                    self._queue.clear()
                    self._queue_added = 0
                    self._queue_executed = 0
            return pack(command_id, frame.ctrl, b"")

        # --- Device info ---------------------------------------------------
        if command_id == CommandID.GET_DEVICE_SN:
            payload = self.serial_number.encode("ascii") + b"\x00"
            return pack(command_id, frame.ctrl, payload)
        if command_id == CommandID.GET_SET_DEVICE_NAME and not is_write:
            payload = self.port.encode("ascii") + b"\x00"
            return pack(command_id, frame.ctrl, payload)
        if command_id == CommandID.GET_DEVICE_VERSION:
            return pack(command_id, frame.ctrl, bytes((1, 9, 0)))

        # --- Color sensor (read returns r, g, b) ---------------------------
        if command_id == CommandID.GET_SET_COLOR_SENSOR and not is_write:
            r, g, b = self._color_sensor
            return pack(command_id, frame.ctrl, bytes((r, g, b)))

        # --- Default fallback -----------------------------------------------
        # A queued write we don't model takes its place in the queue and
        # finishes when it reaches the head. For Get* reads: respond with
        # zeros of a plausible length. For everything else: empty ack.
        if is_queued and is_write:
            queue_index = self.enqueue_action(lambda: None)
            return pack(command_id, frame.ctrl, struct.pack("<Q", queue_index))
        if not is_write:
            return pack(command_id, frame.ctrl, b"\x00" * 8)
        return pack(command_id, frame.ctrl, b"")

    def apply_write(
        self, command_id: int, control: int, is_queued: bool, action: Callable[[], None]
    ) -> bytes:
        """Apply a setting now, or queue it, and return the reply frame."""
        if is_queued:
            queue_index = self.enqueue_action(action)
            return pack(command_id, control, struct.pack("<Q", queue_index))
        with self._lock:
            action()
        return pack(command_id, control, b"")


# ---------------------------------------------------------------------------
# FakeDobotSerial - implements just enough of pyserial.Serial
# ---------------------------------------------------------------------------

# One FakeDobot per port name, shared across all serial.Serial(port=...) calls.
_DOBOTS: dict[str, FakeDobot] = {}
_DOBOTS_LOCK = threading.Lock()


def get_or_create_fake(port: str) -> FakeDobot:
    with _DOBOTS_LOCK:
        bot = _DOBOTS.get(port)
        if bot is None:
            bot = FakeDobot(port=port)
            _DOBOTS[port] = bot
        return bot


class FakeDobotSerial:
    """Drop-in pyserial.Serial replacement that talks to a FakeDobot."""

    def __init__(self, **kwargs) -> None:
        # Mirror real pyserial: a port given at construction opens immediately;
        # otherwise the caller sets .port (and dtr/rts/etc as plain attributes)
        # and calls open() - the closed-first pattern SerialTransport now uses.
        self.port = kwargs.get("port")
        self.timeout = kwargs.get("timeout", 1.0)
        self.write_timeout = kwargs.get("write_timeout", 1.0)
        self._read_buffer = bytearray()
        self._read_lock = threading.Lock()
        self._dobot = None
        self.is_open = False
        if self.port:
            self.open()

    # -- pyserial-like surface ----------------------------------------------

    def open(self) -> None:
        if self._dobot is None:
            self._dobot = get_or_create_fake(self.port or "/dev/sim0")
        self.is_open = True

    def reset_input_buffer(self) -> None:
        with self._read_lock:
            self._read_buffer.clear()

    def reset_output_buffer(self) -> None:
        pass

    def write(self, data: bytes) -> int:
        # The Dobot framing is well-defined - accept the entire packet at
        # once (the transport layer always issues full frames in one write).
        response = self._dobot.handle_frame(bytes(data))
        if response:
            with self._read_lock:
                self._read_buffer += response
        return len(data)

    def flush(self) -> None:
        pass

    def read(self, n: int = 1) -> bytes:
        with self._read_lock:
            received_bytes = bytes(self._read_buffer[:n])
            del self._read_buffer[:n]
        return received_bytes

    def close(self) -> None:
        self.is_open = False


# ---------------------------------------------------------------------------
# Public API: install_simulator() - patch the world
# ---------------------------------------------------------------------------


@dataclass
class SimulatedPortInfo:
    """Minimal stand-in for serial.tools.list_ports.ListPortInfo."""

    device: str
    description: str = "Simulated Dobot Magician"
    vid: int = 0x1A86  # CH340 VID/PID so it shows as a known adapter
    pid: int = 0x7523
    serial_number: str = "SIM-MAGICIAN"


_INSTALLED: bool = False
_INSTALL_LOCK = threading.Lock()


def install_simulator(arms: int | None = None) -> list[str]:
    """Install the simulator backend; return the list of fake port names.

    ``arms`` defaults to the configured value.

    After this returns, any code path that opens ``serial.Serial(port=...)``
    or enumerates ``serial.tools.list_ports.comports()`` will see the fake
    Dobots - including :class:`Dobot`, :func:`Discovery.discover`, and the
    panel GUI.

    Idempotent within a process; calling twice is a no-op.
    """
    global _INSTALLED
    if arms is None:
        arms = get_config()["simulator"]["arms"]
    with _INSTALL_LOCK:
        ports = [f"/dev/sim{i}" for i in range(max(1, int(arms)))]
        # Pre-create the fake arms so they exist even before first connect.
        for port in ports:
            get_or_create_fake(port)

        if _INSTALLED:
            return ports

        # Patch serial.Serial → FakeDobotSerial.
        import serial
        import serial.tools.list_ports as serial_ports

        serial.Serial = FakeDobotSerial  # type: ignore[assignment]

        sim_infos = [SimulatedPortInfo(device=port) for port in ports]

        def simulated_comports():
            return list(sim_infos)

        serial_ports.comports = simulated_comports  # type: ignore[assignment]

        # Bust the broker-reachability cache so the next is_broker_reachable()
        # call re-probes (the panel will start a broker shortly afterwards).
        try:
            from . import broker

            broker._BROKER_CACHE.clear()
        except Exception:
            pass

        _INSTALLED = True
        return ports


def is_simulator_installed() -> bool:
    return _INSTALLED


def stop_all() -> None:
    """Stop background threads on all created fake arms (used by tests)."""
    with _DOBOTS_LOCK:
        for bot in list(_DOBOTS.values()):
            bot.stop()
        _DOBOTS.clear()
