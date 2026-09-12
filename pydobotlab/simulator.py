"""Simulator backend - view & test the panel without a real Dobot.

Activate with::

    pydobotlab-panel --simulator

…or programmatically::

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
* Each fake arm has its own pose (initially home), interpolates toward
  PTP / HOME targets in a daemon thread at ~30 Hz so the panel's pose
  readout actually animates, and tracks a queue index so ``wait_idle``
  works.

It's intentionally additive: nothing in the rest of the library knows
the simulator exists. Without ``--simulator`` (or ``install_simulator()``
in code), behaviour is exactly as before.
"""

from __future__ import annotations

import math
import struct
import threading
from dataclasses import dataclass

from .commands import CommandID
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

# Bounds of the simulated arm's reachable workspace, used to trigger
# PLAN_MOTION_TARGET_OUT_OF_WORKSPACE on out-of-reach PTP targets so
# students can test their error-handling code without real hardware.
SIM_WORKSPACE = {
    "min_radius_mm": 80.0,  # cylindrical reach (sqrt(x^2 + y^2))
    "max_radius_mm": 320.0,
    "z_min_mm": -90.0,
    "z_max_mm": 150.0,
}


# Alarm bit set when a target falls outside SIM_WORKSPACE - matches the
# real firmware's PLAN_MOTION_TARGET_OUT_OF_WORKSPACE code (0x14).
ALARM_OUT_OF_WORKSPACE_CODE = 0x14


# Default speed of the simulated arm (mm/sec) - controls how visibly the
# panel's pose readout animates between waypoints.
DEFAULT_SPEED_MM_PER_S = 200.0
DEFAULT_JOG_SPEED_MM_PER_S = 80.0
DEFAULT_JOG_SPEED_DEG_PER_S = 60.0
DEFAULT_TICK_HZ = 30.0


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
    queue_index: int = 0  # the queued cmd index this target finishes


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
        speed_mm_per_s: float = DEFAULT_SPEED_MM_PER_S,
        tick_hz: float = DEFAULT_TICK_HZ,
        serial_number: str = "SIM-MAGICIAN",
    ) -> None:
        self.port = port
        self.serial_number = serial_number
        self._state = ArmState()
        self._target: MotionTarget | None = None
        # Multi-stage motions (e.g. HOME) traverse a list of waypoints; the
        # current one lives in _target, the rest in _pending_targets.
        self._pending_targets: list[MotionTarget] = []
        # While set, the sim_loop nudges the pose in this direction every
        # tick. set_jog_cmd(IDLE) clears it.
        self._jog: ActiveJog | None = None
        # Internal "100% velocity" baselines. Effective speed every tick is
        # baseline * (vel_ratio / 100), so the panel's speed slider directly
        # controls how fast jogs and PTPs run - same as a real arm.
        self._jog_baseline_mm = DEFAULT_JOG_SPEED_MM_PER_S
        self._jog_baseline_deg = DEFAULT_JOG_SPEED_DEG_PER_S
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
                # 1. Active JOG - nudge pose every tick. JOG cancels any
                #    pending PTP target (manual override beats automation).
                if self._jog is not None:
                    self._apply_jog_step(self._jog)
                # 2. Multi-stage / single-target interpolation.
                elif self._target is not None:
                    self._step_toward_target()
            self._stop.wait(self._tick_seconds)

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

    def _step_toward_target(self) -> None:
        """Advance current target by one tick; pop the next one when reached."""
        state, target = self._state, self._target
        if target is None:
            return
        dx, dy, dz = target.x - state.x, target.y - state.y, target.z - state.z
        distance = max((dx * dx + dy * dy + dz * dz) ** 0.5, 1e-9)
        step = self._speed * self._tick_seconds
        if distance <= step:
            state.x, state.y, state.z, state.r = target.x, target.y, target.z, target.r
            if self._pending_targets:
                self._target = self._pending_targets.pop(0)
            else:
                self._queue_executed = max(self._queue_executed, target.queue_index)
                self._target = None
        else:
            state.x += dx * (step / distance)
            state.y += dy * (step / distance)
            state.z += dz * (step / distance)
            # R rotates fast - interpolate proportionally to XY/Z progress.
            state.r += (target.r - state.r) * (step / distance)

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=1.0)

    # ---- helpers used by the frame handler --------------------------------

    def enqueue_home(self) -> int:
        """Multi-stage homing - lift Z, rotate to home XY, descend.

        Mimics the visible behaviour of a real Magician: it first lifts
        out of the work area, then swings the base around to align with
        the home position, then drops down to the home Z.
        """
        with self._lock:
            self._queue_added += 1
            queue_index = self._queue_added
            state = self._state
            home_x, home_y, home_z, home_r = 200.0, 0.0, 50.0, 0.0
            lift_z = max(state.z, home_z) + 60.0  # safe altitude above both poses
            stages = [
                # 1. Lift Z while keeping current XY/R.
                MotionTarget(x=state.x, y=state.y, z=lift_z, r=state.r, queue_index=queue_index),
                # 2. Swing the base to align with home XY (still up high).
                MotionTarget(x=home_x, y=home_y, z=lift_z, r=home_r, queue_index=queue_index),
                # 3. Descend to the home Z.
                MotionTarget(x=home_x, y=home_y, z=home_z, r=home_r, queue_index=queue_index),
            ]
            self._target = stages[0]
            self._pending_targets = stages[1:]
            return queue_index

    def set_motion_target(self, x: float, y: float, z: float, r: float) -> int:
        with self._lock:
            self._queue_added += 1
            queue_index = self._queue_added
            if not self.is_in_workspace(x, y, z):
                # The real firmware behaviour: queue index advances (so
                # wait_for() returns), but the workspace alarm bit is set
                # so the pydobotlab waiters detect the failure and raise
                # DobotKinematicError on the script side.
                self._alarms[ALARM_OUT_OF_WORKSPACE_CODE // 8] |= 1 << (
                    ALARM_OUT_OF_WORKSPACE_CODE % 8
                )
                self._queue_executed = max(self._queue_executed, queue_index)
                self._target = None
                return queue_index
            self._target = MotionTarget(x=x, y=y, z=z, r=r, queue_index=queue_index)
            self._pending_targets.clear()
            return queue_index

    @staticmethod
    def is_in_workspace(x: float, y: float, z: float) -> bool:
        radius = math.sqrt(x * x + y * y)
        workspace = SIM_WORKSPACE
        return (
            workspace["min_radius_mm"] <= radius <= workspace["max_radius_mm"]
            and workspace["z_min_mm"] <= z <= workspace["z_max_mm"]
        )

    def complete_queued_command(self) -> int:
        """For queued commands that don't move the arm - bump the counter."""
        with self._lock:
            self._queue_added += 1
            self._queue_executed = self._queue_added  # instantly "done"
            return self._queue_added

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
                    # Manual jog cancels any in-flight automated motion.
                    self._target = None
                    self._pending_targets.clear()
                if is_queued:
                    self._queue_added += 1
                    self._queue_executed = self._queue_added
                    return pack(command_id, frame.ctrl, struct.pack("<Q", self._queue_added))
            return pack(command_id, frame.ctrl, b"")

        # --- Movement-rate / jog-rate (controlled by the panel speed slider)
        # Each one stores a (vel_ratio, acc_ratio) pair as a percentage that
        # scales the effective motion speed used by _run_motion_loop.
        if command_id == CommandID.GET_SET_PTP_COMMON_PARAMS:
            if is_write and len(params) >= 8:
                velocity, acceleration = struct.unpack("<2f", params[:8])
                with self._lock:
                    self._ptp_vel_ratio = max(0.0, min(100.0, float(velocity)))
                    self._ptp_acc_ratio = max(0.0, min(100.0, float(acceleration)))
                    self._speed = self._ptp_baseline_mm * self._ptp_vel_ratio / 100.0
                if is_queued:
                    self._queue_added += 1
                    self._queue_executed = self._queue_added
                    return pack(command_id, frame.ctrl, struct.pack("<Q", self._queue_added))
                return pack(command_id, frame.ctrl, b"")
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
                with self._lock:
                    self._jump_height = float(height)
                    self._jump_zlimit = float(zlimit)
                if is_queued:
                    self._queue_added += 1
                    self._queue_executed = self._queue_added
                    return pack(command_id, frame.ctrl, struct.pack("<Q", self._queue_added))
                return pack(command_id, frame.ctrl, b"")
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
                with self._lock:
                    self._jog_vel_ratio = max(0.0, min(100.0, float(velocity)))
                    self._jog_acc_ratio = max(0.0, min(100.0, float(acceleration)))
                    self._jog_speed_mm = self._jog_baseline_mm * self._jog_vel_ratio / 100.0
                    self._jog_speed_deg = self._jog_baseline_deg * self._jog_vel_ratio / 100.0
                if is_queued:
                    self._queue_added += 1
                    self._queue_executed = self._queue_added
                    return pack(command_id, frame.ctrl, struct.pack("<Q", self._queue_added))
                return pack(command_id, frame.ctrl, b"")
            else:
                with self._lock:
                    return pack(
                        command_id,
                        frame.ctrl,
                        struct.pack("<2f", self._jog_vel_ratio, self._jog_acc_ratio),
                    )

        # --- Wait ----------------------------------------------------------
        if command_id == CommandID.SET_WAIT_CMD and is_queued:
            return pack(command_id, frame.ctrl, struct.pack("<Q", self.complete_queued_command()))

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
            if command_id == CommandID.SET_QUEUED_CMD_CLEAR:
                with self._lock:
                    self._queue_added = 0
                    self._queue_executed = 0
                    self._target = None
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
        # For any queued write we don't model explicitly: bump the counter
        # and acknowledge. For Get* reads: respond with zeros of a plausible
        # length. For everything else: empty ack.
        if is_queued and is_write:
            return pack(command_id, frame.ctrl, struct.pack("<Q", self.complete_queued_command()))
        if not is_write:
            return pack(command_id, frame.ctrl, b"\x00" * 8)
        return pack(command_id, frame.ctrl, b"")


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


def install_simulator(arms: int = 2) -> list[str]:
    """Install the simulator backend; return the list of fake port names.

    After this returns, any code path that opens ``serial.Serial(port=...)``
    or enumerates ``serial.tools.list_ports.comports()`` will see the fake
    Dobots - including :class:`Dobot`, :func:`Discovery.discover`, and the
    panel GUI.

    Idempotent within a process; calling twice is a no-op.
    """
    global _INSTALLED
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
