"""High-level :class:`Dobot` API.

The public method names and signatures match the official **DobotLab Coding
Manual**'s "Dobot Magician" section exactly (3.6.1 - 3.6.28). Where DobotLab
itself doesn't expose something useful - batched/lazy queue execution,
real-time pose streaming, structured alarm sets, multi-arm - we add it on
top, alongside the official surface.

One :class:`Dobot` instance = one physical arm. Multi-arm choreography is
the application's job, not the library's.
"""

from __future__ import annotations

import re
import struct
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from queue import Queue

from .alarms import Alarm, AlarmSet, decode_alarms
from .commands import CommandID
from .discovery import find_free_port
from .errors import (
    DobotAlarmError,
    DobotConnectionError,
    DobotKinematicError,
    DobotTimeoutError,
)
from .protocol import (
    CTRL_QUEUED,
    CTRL_RW,
    Frame,
    JOGCmd,
    JogMode,
    PTPMode,
    pack_floats,
    pack_u8,
    pack_u32,
    unpack_floats,
    unpack_u64,
)
from .queue import BatchState, batch_context
from .transport import BrokerTransport, SerialTransport

# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Pose:
    """Snapshot returned by :meth:`Dobot.get_pose`.

    Cartesian fields are millimetres / degrees; joint fields are degrees.

    Iterates as ``(x, y, z, r, jointAngle)`` to match the DobotLab official
    return shape - so::

        x, y, z, r, joints = bot.get_pose()

    works exactly as in the official manual. The richer attribute access
    (``pose.x`` ... ``pose.j4``) is also available.
    """

    x: float
    y: float
    z: float
    r: float
    j1: float
    j2: float
    j3: float
    j4: float

    def __str__(self) -> str:
        """Readable coordinates in mm and angles in degrees, rounded for display."""
        joint_angles = ", ".join(f"{angle:.2f}" for angle in self.joints)
        return (
            f"Pose(x={self.x:.2f}, y={self.y:.2f}, z={self.z:.2f}, "
            f"r={self.r:.2f}, joints=[{joint_angles}])"
        )

    @property
    def joints(self) -> list[float]:
        """``[j1, j2, j3, j4]`` - the ``jointAngle`` element of DobotLab's tuple."""
        return [self.j1, self.j2, self.j3, self.j4]

    def __iter__(self):
        yield self.x
        yield self.y
        yield self.z
        yield self.r
        yield self.joints

    def as_xyzr(self) -> tuple[float, float, float, float]:
        return (self.x, self.y, self.z, self.r)

    def as_joints(self) -> tuple[float, float, float, float]:
        return (self.j1, self.j2, self.j3, self.j4)


# ---------------------------------------------------------------------------
# IO-string parsing helper
# ---------------------------------------------------------------------------

# DobotLab references IO ports by string ("DO_01" .. "DO_20", "DI_01" ..
# "DI_20"). The label distinguishes intent (output vs input vs PWM vs ADC)
# but the underlying address is the same integer 1..20. We accept both the
# string form (preferred, matches the manual) and the bare integer for
# advanced callers.

IO_PORT_PATTERN = re.compile(r"^(DO|DI|AI|AD)_?(\d{1,2})$", re.IGNORECASE)


def parse_io_port(reference: str | int) -> int:
    """Convert a DobotLab IO label (``"DO_01"``) or integer to a port in 1..20."""
    port_number = None
    if isinstance(reference, int):
        port_number = reference
    elif isinstance(reference, str):
        label = reference.strip()
        match = IO_PORT_PATTERN.fullmatch(label)
        if match:
            port_number = int(match.group(2))
        elif label.isdecimal():
            port_number = int(label)
    if port_number is not None and 1 <= port_number <= 20:
        return port_number
    raise ValueError(
        f"unrecognised IO reference {reference!r}; expected 'DO_01'..'DO_20' or an integer 1..20"
    )


# ---------------------------------------------------------------------------
# Motion-failure alarm codes. When any of these bits is set, the firmware
# is telling us a motion command couldn't be planned or executed. Used by
# the wait_for / wait_idle / move_to / set_home loops to raise
# :class:`DobotKinematicError` instead of silently completing.
MOTION_ALARM_CODES: frozenset[int] = frozenset(
    {
        Alarm.PLAN_INVERSE_RESOLVE,
        Alarm.PLAN_INVERSE_LIMIT,
        Alarm.PLAN_CURRENT_JOINT_OUT_OF_RANGE,
        Alarm.PLAN_MOTION_TARGET_OUT_OF_WORKSPACE,
        Alarm.PLAN_IN_SINGULARITY_ZONE,
        Alarm.KINEMATIC_SINGULARITY,
        Alarm.KINEMATIC_TARGET_OUT_OF_WORKSPACE,
        Alarm.KINEMATIC_INVERSE_LIMIT,
        Alarm.LIMIT_POS_J1,
        Alarm.LIMIT_POS_J2,
        Alarm.LIMIT_POS_J3,
        Alarm.LIMIT_POS_J4,
        Alarm.LIMIT_NEG_J1,
        Alarm.LIMIT_NEG_J2,
        Alarm.LIMIT_NEG_J3,
        Alarm.LIMIT_NEG_J4,
    }
)


# ---------------------------------------------------------------------------
# Dobot
# ---------------------------------------------------------------------------


class Magician:
    """Pure-Python control surface for a single Dobot Magician.

    The public methods named in the DobotLab Coding Manual (sections 3.6.1
    through 3.6.28) are exposed verbatim. Other methods (``move_to``,
    ``batch``, ``wait_idle``, ``get_alarms``, ``start_pose_stream``, ...) are
    additions that DobotLab does not natively provide.

    See module docstring for the connection model (auto-pick by default).
    """

    # ------------------------------------------------------------------
    # Class-level constants exposed to user code (DobotLab style:
    # ``magician.Stepper1`` / ``magician.Stepper2``).
    # ------------------------------------------------------------------
    Stepper1: int = 0
    Stepper2: int = 1

    # ------------------------------------------------------------------
    # Construction / lifecycle
    # ------------------------------------------------------------------

    def __init__(
        self,
        port: str | None = None,
        baudrate: int = 115200,
        timeout: float = 1.0,
        *,
        auto_start_queue: bool = True,
        only_known_adapters: bool = False,
        via_broker: bool | str = "auto",
        broker_host: str = "127.0.0.1",
        broker_port: int = 8765,
    ) -> None:
        """\
        ``via_broker``:
            - ``"auto"`` (default) - at connect time, probe localhost for a
              running :class:`pydobotlab.broker.DobotBroker` and route through
              it if reachable. Otherwise open the serial port directly. This
              lets the control-panel GUI and a student script share an arm.
            - ``True`` - require the broker; raise if unreachable.
            - ``False`` - never use the broker (always direct serial).
        """
        self._explicit_port = port
        self._baudrate = baudrate
        self._timeout = timeout
        self._auto_start_queue = auto_start_queue
        self._only_known_adapters = only_known_adapters
        self._via_broker = via_broker
        self._broker_host = broker_host
        self._broker_port = broker_port
        self._transport: SerialTransport | BrokerTransport | None = None
        self._batch_state = BatchState()
        self._last_queued_index: int = 0
        self._index_lock = threading.Lock()
        self._pose_stream_stop: threading.Event | None = None
        self._pose_stream_thread: threading.Thread | None = None
        # get_color_sensor() takes no port; remember the last-configured one.
        self._color_sensor_port: int = 1

    def connect(self) -> None:
        """Resolve the port (auto-pick if unset), open the line, prep the queue.

        If a :class:`pydobotlab.broker.DobotBroker` is reachable on localhost
        (the panel runs one), route through it instead of opening the serial
        port directly. Override with ``via_broker=False``.
        """
        if self._transport is None:
            from .broker import is_broker_reachable, list_broker_ports

            use_broker = False
            if self._via_broker is True:
                if not is_broker_reachable(self._broker_host, self._broker_port):
                    raise DobotConnectionError(
                        f"via_broker=True but no broker reachable at "
                        f"{self._broker_host}:{self._broker_port}"
                    )
                use_broker = True
            elif self._via_broker == "auto" and is_broker_reachable(
                self._broker_host, self._broker_port
            ):
                use_broker = True

            port = self._explicit_port
            if port is None:
                if use_broker:
                    # Ask the broker which ports it owns; pick the first free.
                    try:
                        broker_ports = list_broker_ports(
                            self._broker_host,
                            self._broker_port,
                        )
                    except Exception:
                        broker_ports = []
                    port = broker_ports[0] if broker_ports else None
                if port is None:
                    port = find_free_port(only_known_adapters=self._only_known_adapters)
                if port is None:
                    raise DobotConnectionError(
                        "Dobot() with no explicit port could not auto-pick: "
                        "no free Dobot answered a probe on any enumerated "
                        "serial port"
                    )

            if use_broker:
                self._transport = BrokerTransport(
                    port,
                    self._baudrate,
                    self._timeout,
                    broker_host=self._broker_host,
                    broker_port=self._broker_port,
                )
            else:
                self._transport = SerialTransport(
                    port,
                    self._baudrate,
                    self._timeout,
                )
        try:
            self._transport.open()
            if self._auto_start_queue:
                self.clear_queue()
                self.start_queue()
        except Exception:
            self._transport.close()
            self._transport = None
            raise

    def disconnect(self) -> None:
        self.stop_pose_stream()
        if self._transport is not None:
            try:
                if self._transport.is_open:
                    self.stop_queue()
            except Exception:
                pass
            self._transport.close()

    def __enter__(self) -> Dobot:
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.disconnect()

    @property
    def port(self) -> str | None:
        if self._transport is not None:
            return self._transport.port
        return self._explicit_port

    @property
    def is_open(self) -> bool:
        return self._transport is not None and self._transport.is_open

    # ------------------------------------------------------------------
    # Low-level send helpers
    # ------------------------------------------------------------------

    def send_command(
        self,
        command_id: int,
        params: bytes = b"",
        *,
        write: bool,
        queued: bool = False,
    ) -> Frame:
        """Send a protocol command and return its decoded response.

        Prefer the named robot methods for normal use. For custom queued
        writes, use :meth:`queue_command` so :meth:`wait_idle` tracks them.
        """
        if self._transport is None or not self._transport.is_open:
            raise DobotConnectionError(
                "Dobot is not connected; call connect() or use a `with` block"
            )
        control = (CTRL_RW if write else 0) | (CTRL_QUEUED if queued else 0)
        return self._transport.send_frame(int(command_id), control, params)

    def write_command(self, command_id: int, params: bytes = b"") -> Frame:
        """Write a command immediately, bypassing the firmware queue."""
        return self.send_command(command_id, params, write=True, queued=False)

    def queue_command(self, command_id: int, params: bytes = b"") -> int:
        """Queue a write and track its index for :meth:`wait_idle`."""
        frame = self.send_command(command_id, params, write=True, queued=True)
        index = unpack_u64(frame.params)
        with self._index_lock:
            if index > self._last_queued_index:
                self._last_queued_index = index
        return index

    def read_command(self, command_id: int, params: bytes = b"") -> Frame:
        """Read a command response without adding to the firmware queue."""
        return self.send_command(command_id, params, write=False, queued=False)

    # ==================================================================
    # OFFICIAL DobotLab API (sections 3.6.1 - 3.6.28)
    # Names and signatures match the DobotLab Coding Manual verbatim.
    # ==================================================================

    # ---- 3.6.1  Point-to-point Movement -------------------------------
    def ptp(self, mode: int, x: float, y: float, z: float, r: float) -> int:
        """Move to ``(x, y, z, r)`` in PTP ``mode`` (0..9). Queues a move."""
        params = bytes((int(mode),)) + pack_floats(x, y, z, r)
        return self.queue_command(CommandID.SET_PTP_CMD, params)

    # ---- 3.6.2  Set Slideway State and Version ------------------------
    def set_device_withl(self, enable: bool, version: int = 0) -> int:
        """Enable/disable the slideway and declare its hardware version (0=V1, 1=V2)."""
        return self.queue_command(
            CommandID.GET_SET_DEVICE_WITH_L,
            pack_u8(1 if enable else 0, int(version)),
        )

    # ---- 3.6.3  Set Speed of Slideway ---------------------------------
    def set_ptpl_params(self, vel: float, accel: float) -> int:
        """Slideway max velocity / acceleration (each as a percentage 1..100)."""
        return self.queue_command(
            CommandID.GET_SET_PTP_L_PARAMS,
            pack_floats(vel, accel),
        )

    # ---- 3.6.4  PTP with Slideway -------------------------------------
    def set_ptpwithl_cmd(self, mode: int, x: float, y: float, z: float, r: float, l: float) -> int:
        """PTP move that also drives the slideway to ``l`` (mm)."""
        params = bytes((int(mode),)) + pack_floats(x, y, z, r, l)
        return self.queue_command(CommandID.SET_PTP_WITH_L_CMD, params)

    # ---- 3.6.5  Set R-axis Angle --------------------------------------
    def set_r(self, r: float) -> int:
        """Rotate the R axis to ``r`` (degrees) without moving X/Y/Z."""
        pose = self.get_pose()
        return self.ptp(PTPMode.MOVJ_XYZ, pose.x, pose.y, pose.z, r)

    # ---- 3.6.6  Set Movement Rate (PROPERTY) --------------------------
    @property
    def motion_params(self) -> tuple[float, float]:
        """``(vel, acc)`` global PTP velocity / acceleration ratios.

        DobotLab usage: ``magician.motion_params = 50, 50``.
        """
        frame = self.read_command(CommandID.GET_SET_PTP_COMMON_PARAMS)
        v, a = unpack_floats(frame.params[:8])
        return (v, a)

    @motion_params.setter
    def motion_params(self, value: tuple[float, float]) -> None:
        vel, acc = value
        self.queue_command(
            CommandID.GET_SET_PTP_COMMON_PARAMS,
            pack_floats(float(vel), float(acc)),
        )

    # ---- 3.6.7  Set Jump Movement Params (PROPERTY) -------------------
    @property
    def jump_params(self) -> tuple[float, float]:
        """``(zlimit, height)`` for JUMP-mode moves.

        DobotLab usage: ``magician.jump_params = 100, 20  # zlimit, height``.
        """
        frame = self.read_command(CommandID.GET_SET_PTP_JUMP_PARAMS)
        # Wire order is (jumpHeight, zLimit); we expose (zlimit, height).
        height, zlimit = unpack_floats(frame.params[:8])
        return (zlimit, height)

    @jump_params.setter
    def jump_params(self, value: tuple[float, float]) -> None:
        zlimit, height = value
        # Wire order is (jumpHeight, zLimit) - flip back.
        self.queue_command(
            CommandID.GET_SET_PTP_JUMP_PARAMS,
            pack_floats(float(height), float(zlimit)),
        )

    # ---- 3.6.8  Set Mode of IO Port -----------------------------------
    def set_multiplexing(self, io, multiplex: int) -> int:
        """Configure ``io`` (e.g. ``"DO_01"``) as DO/PWM/DI/ADC/PullUp/PullDn."""
        port = parse_io_port(io)
        return self.queue_command(
            CommandID.GET_SET_IO_MULTIPLEXING,
            pack_u8(port, int(multiplex)),
        )

    # ---- 3.6.9  Set Frequency and Duty Cycle of PWM Output Port ------
    def set_pwm(self, io, freq: float, cycle: float) -> int:
        """Set PWM frequency (Hz, 10..1MHz) and duty cycle (0..100 %) on ``io``."""
        port = parse_io_port(io)
        return self.queue_command(
            CommandID.GET_SET_IO_PWM,
            pack_u8(port) + pack_floats(float(freq), float(cycle)),
        )

    # ---- 3.6.10  Set Digital Output Port -----------------------------
    def set_do(self, io, level: int) -> int:
        """Drive digital output ``io`` (e.g. ``"DO_01"``) low (0) or high (1)."""
        port = parse_io_port(io)
        return self.queue_command(
            CommandID.GET_SET_IO_DO,
            pack_u8(port, 1 if int(level) else 0),
        )

    # ---- 3.6.11  Get Digital Signal -----------------------------------
    def get_di(self, io) -> int:
        """Read digital input ``io`` - returns 0 (low) or 1 (high)."""
        port = parse_io_port(io)
        frame = self.read_command(CommandID.GET_IO_DI, pack_u8(port))
        return int(frame.params[1])

    # ---- 3.6.12  Get Analog Signal ------------------------------------
    def get_adc(self, io) -> int:
        """Read analog input ``io`` - returns 0..4095."""
        port = parse_io_port(io)
        frame = self.read_command(CommandID.GET_IO_ADC, pack_u8(port))
        return struct.unpack("<H", frame.params[1:3])[0]

    # ---- 3.6.13  Set End Suction Cup ----------------------------------
    def set_endeffector_suctioncup(self, enable: bool, on: bool) -> int:
        """Suction-cup state.

        ``enable`` arms the pump; ``on`` selects suck (True) vs release (False).
        """
        return self.queue_command(
            CommandID.GET_SET_END_EFFECTOR_SUCTION_CUP,
            pack_u8(1 if enable else 0, 1 if on else 0),
        )

    # ---- 3.6.14  Set End Gripper --------------------------------------
    def set_endeffector_gripper(self, enable: bool, on: bool) -> int:
        """Gripper state. ``on=True`` grips; ``on=False`` releases."""
        return self.queue_command(
            CommandID.GET_SET_END_EFFECTOR_GRIPPER,
            pack_u8(1 if enable else 0, 1 if on else 0),
        )

    # ---- 3.6.15  Set Photoelectric Sensor -----------------------------
    def set_infrared_sensor(self, port: int, enable: bool, version: int = 1) -> int:
        """Configure an IR / photoelectric sensor on GP1/GP2/GP4/GP5."""
        return self.queue_command(
            CommandID.GET_SET_INFRARED_SENSOR,
            pack_u8(int(port), 1 if enable else 0, int(version)),
        )

    # ---- 3.6.16  Get Value of Photoelectric Sensor --------------------
    def get_infrared_sensor(self, port: int) -> int:
        """0 = nothing detected, 1 = object detected."""
        frame = self.read_command(CommandID.GET_SET_INFRARED_SENSOR, pack_u8(int(port)))
        return int(frame.params[0])

    # ---- 3.6.17  Set Color Sensor -------------------------------------
    def set_color_sensor(self, port: int, enable: bool, version: int = 0) -> int:
        """Configure the colour sensor on a specific port. Stores ``port`` so
        :meth:`get_color_sensor` (which takes no argument in DobotLab) knows
        which sensor to query."""
        self._color_sensor_port = int(port)
        return self.queue_command(
            CommandID.GET_SET_COLOR_SENSOR,
            pack_u8(int(port), 1 if enable else 0, int(version)),
        )

    # ---- 3.6.18  Get Value of Color Sensor ----------------------------
    def get_color_sensor(self) -> tuple[int, int, int]:
        """Read ``(r, g, b)`` from the most-recently-configured colour sensor."""
        frame = self.read_command(
            CommandID.GET_SET_COLOR_SENSOR,
            pack_u8(self._color_sensor_port),
        )
        return int(frame.params[0]), int(frame.params[1]), int(frame.params[2])

    # ---- 3.6.19  Wait N Seconds ---------------------------------------
    def wait(self, second: float) -> int:
        """Insert a pause of ``second`` seconds into the firmware queue."""
        ms = max(0, int(round(float(second) * 1000)))
        return self.queue_command(CommandID.SET_WAIT_CMD, pack_u32(ms))

    # ---- 3.6.20  Set Home ---------------------------------------------
    def set_home(
        self,
        *,
        wait: bool = True,
        timeout: float | None = 60.0,
        raise_on_alarm: bool = True,
    ) -> int:
        """Move the arm to its home position. Blocks until done unless ``wait=False``.

        If a motion-failure alarm fires (typically only if home itself is
        unreachable from the current pose), raises :class:`DobotKinematicError`.
        """
        index = self.queue_command(CommandID.SET_HOME_CMD, pack_u32(0))
        if wait:
            self.wait_for(index, timeout=timeout, raise_on_alarm=raise_on_alarm)
        return index

    # ---- 3.6.21  Get Current Pose -------------------------------------
    def get_pose(self) -> Pose:
        """Returns ``(x, y, z, r, jointAngle)`` (iterable) or ``Pose`` (attrs)."""
        frame = self.read_command(CommandID.GET_POSE)
        x, y, z, r, j1, j2, j3, j4 = unpack_floats(frame.params[:32])
        return Pose(x, y, z, r, j1, j2, j3, j4)

    # ---- 3.6.22  Get Pose of Slideway ---------------------------------
    def get_posel(self) -> float:
        """Slideway position in millimetres."""
        frame = self.read_command(CommandID.GET_POSE_L)
        return unpack_floats(frame.params[:4])[0]

    # ---- 3.6.23  Clear Alarm ------------------------------------------
    def clear_alarm(self, *, verify: bool = False, settle: float = 0.15) -> None:
        """Clear all active alarms.

        When ``verify=True``, re-reads the alarm bitmask after a brief
        settle delay and raises :class:`DobotAlarmError` if any motion
        alarm is *still* set - the firmware honoured the clear, but the
        underlying physical condition (joint still mashed against a limit,
        sensor still faulting, etc.) reasserted it immediately. The
        student needs to fix the *physical* condition first (jog away from
        the limit, re-home, ...).
        """
        self.write_command(CommandID.CLEAR_ALL_ALARMS_STATE)
        if not verify:
            return
        time.sleep(settle)
        active = self.get_alarms()
        # Only motion-related bits count as "physical condition still active".
        persistent = [
            (int(a), name, line)
            for a, name, line in zip(active.alarms, active.names(), active.format(), strict=True)
            if 0x10 <= int(a) <= 0x77
        ]
        if persistent:
            lines = [line for _, _, line in persistent]
            raise DobotAlarmError(
                alarms=[name for _, name, _ in persistent],
                message=(
                    "alarm reasserted itself after clear - the physical "
                    "condition is still active:\n  - " + "\n  - ".join(lines)
                ),
            )

    # ---- 3.6.24  Get Speed of Arm -------------------------------------
    def get_arm_speed_ratio(self, mode: int) -> float:
        """Speed-rate percent for ``mode`` (0 = jog, 1 = PTP)."""
        if int(mode) == 0:
            frame = self.read_command(CommandID.GET_SET_JOG_COMMON_PARAMS)
        else:
            frame = self.read_command(CommandID.GET_SET_PTP_COMMON_PARAMS)
        # Both endpoints return (vel_ratio, acc_ratio); we surface the velocity.
        v, _ = unpack_floats(frame.params[:8])
        return float(v)

    def set_jog_common_params(self, vel_ratio: float, acc_ratio: float) -> int:
        """Global JOG velocity / acceleration percentage (0..100).

        DobotLab's panel sends this whenever the speed slider moves, so
        jog buttons honour the same speed setting that PTP commands do.
        """
        return self.queue_command(
            CommandID.GET_SET_JOG_COMMON_PARAMS,
            pack_floats(float(vel_ratio), float(acc_ratio)),
        )

    def get_jog_common_params(self) -> tuple[float, float]:
        """Read back the current JOG (vel_ratio, acc_ratio)."""
        frame = self.read_command(CommandID.GET_SET_JOG_COMMON_PARAMS)
        v, a = unpack_floats(frame.params[:8])
        return (float(v), float(a))

    # ---- 3.6.25  Set Lost-step Threshold ------------------------------
    def set_lost_step_params(self, value: float) -> int:
        """Lost-step alarm threshold; firing it raises a LOST_STEP_* alarm."""
        return self.queue_command(
            CommandID.GET_SET_LOST_STEP_PARAMS,
            pack_floats(float(value)),
        )

    # ---- 3.6.26  Perform Lost-step Detection --------------------------
    def set_lost_step_cmd(self) -> int:
        """Trigger a lost-step detection pass."""
        return self.queue_command(CommandID.SET_LOST_STEP_CMD, b"")

    # ---- 3.6.27  Check Lost-step Results ------------------------------
    def get_lost_step_result(self) -> list[str]:
        """List of currently active alarm names (per the official return shape)."""
        return self.get_alarms().names()

    # ---- 3.6.28  Set Speed of Conveyor and Move -----------------------
    def set_converyor(self, index: int, enable: bool, speed: float) -> int:
        """Drive a stepper-conveyor.

        Note: the official function name has a typo (``set_converyor`` rather
        than ``set_conveyor``); we match it verbatim and additionally expose
        :meth:`set_conveyor` as an alias.

        ``index``: ``magician.Stepper1`` (0) or ``magician.Stepper2`` (1).
        ``speed``: pulses/sec; negative reverses direction.
        """
        params = pack_u8(int(index), 1 if enable else 0) + struct.pack(
            "<i", int(round(float(speed)))
        )
        return self.queue_command(CommandID.SET_E_MOTOR, params)

    # Sane-name alias for the official typo.
    set_conveyor = set_converyor

    # ==================================================================
    # Additions on top of the official surface
    # (lazy-batch execution, alarms, pose stream, queue control, JOG,
    #  continuous-path drawing)
    # ==================================================================

    # ---- Additional end-effector command -----------------------------
    def set_endeffector_laser(self, enable: bool, on: bool) -> int:
        """Enable the laser driver and set its output; return the queue index."""
        return self.queue_command(
            CommandID.GET_SET_END_EFFECTOR_LASER, pack_u8(int(enable), int(on))
        )

    # ---- Continuous Path (CP) ----------------------------------------
    # CP is in the firmware protocol (cmd IDs 90/91) but DobotLab's
    # Python wrapper doesn't expose it in section 3.6 - every PTP
    # MOVL_XYZ trajectory there decelerates to zero between segments,
    # which produces visible pauses when drawing. pydobotlab adds cp()
    # so a chain of segments blends into one smooth trajectory.
    def set_cp_params(
        self,
        plan_acc: float,
        junction_vel: float,
        acc: float = 0.0,
        *,
        real_time_track: bool = False,
    ) -> int:
        """Tune Continuous Path execution.

        CP is the firmware's "blend consecutive moves into one smooth
        trajectory" mode - exactly what you want for drawing, engraving,
        or any path where PTP's deceleration-to-zero between segments is
        the wrong behaviour. ``cp()`` queues each segment; the firmware
        looks ahead in the queue to compute corner velocities.

        Parameters
        ----------
        plan_acc:
            Planning acceleration (mm/s²) the trajectory planner uses
            when smoothing corner transitions. Higher = sharper corners.
        junction_vel:
            Maximum velocity (mm/s) preserved through a corner. Lower =
            slower corners, smoother arcs.
        acc:
            Execution acceleration limit (mm/s²). ``0`` means "use the
            firmware default".
        real_time_track:
            When True, the firmware streams a CP execution position back
            via the alarms register; almost no one uses this. Default
            False.
        """
        return self.queue_command(
            CommandID.GET_SET_CP_PARAMS,
            pack_floats(float(plan_acc), float(junction_vel), float(acc))
            + pack_u8(1 if real_time_track else 0),
        )

    def cp(
        self,
        x: float,
        y: float,
        z: float,
        *,
        velocity: float = 100.0,
        mode: int = 1,
    ) -> int:
        """Queue one Continuous Path segment.

        Unlike a chain of PTP MOVL_XYZ moves, the arm does NOT decelerate
        to zero between consecutive ``cp()`` calls - the firmware blends
        them into a single smooth trajectory. This is what gives a drawn
        line a clean visual flow instead of the visible little pauses
        DobotLab shows on a per-PTP-segment program.

        Parameters
        ----------
        x, y, z:
            Cartesian target (mm). Absolute by default.
        velocity:
            Path velocity in mm/s. Holds across consecutive cp() calls.
        mode:
            ``1`` = absolute (default), ``0`` = relative. The official
            protocol calls these ``CPRelative`` (0) and ``CPAbsolute``
            (1); we match that convention.

        Returns
        -------
        int
            Queued-command index.

        Notes
        -----
        Call :meth:`set_cp_params` once at the start of a drawing program
        to tune corner smoothness. If you don't, the firmware uses a
        conservative default and your corners will look rounded.
        """
        return self.queue_command(
            CommandID.SET_CP_CMD,
            pack_u8(int(mode)) + pack_floats(float(x), float(y), float(z), float(velocity)),
        )

    # ---- Alarms (richer than the official just-a-list view) ----------
    def get_alarms(self) -> AlarmSet:
        """Read and decode the firmware's 16-byte alarm bitmask."""
        frame = self.read_command(CommandID.GET_ALARMS_STATE)
        return decode_alarms(frame.params)

    def ensure_no_alarms(self) -> None:
        """Raise :class:`DobotAlarmError` if any alarm is currently active."""
        alarms = self.get_alarms()
        if alarms:
            raise DobotAlarmError(alarms.names())

    # ---- Convenience: blocking move_to() that waits for queue ---------
    def move_to(
        self,
        x: float,
        y: float,
        z: float,
        r: float = 0.0,
        *,
        mode: PTPMode = PTPMode.MOVJ_XYZ,
        wait: bool = True,
        timeout: float | None = 30.0,
        raise_on_alarm: bool = True,
    ) -> int:
        """Queue a PTP move and (by default) block until it completes.

        If the firmware refuses the target - typically because it's outside
        the arm's reachable workspace - :class:`DobotKinematicError` is
        raised. To retry, call :meth:`clear_alarm` first.
        """
        index = self.ptp(int(mode), x, y, z, r)
        if wait:
            self.wait_for(index, timeout=timeout, raise_on_alarm=raise_on_alarm)
        return index

    # ---- JOG (live, non-trajectory motion) ----------------------------
    def jog(self, cmd, mode=JogMode.COORDINATE) -> Frame:
        """Start (or stop) a JOG using an IMMEDIATE frame.

        Sent immediate (not queued) so the IDLE-on-release reaches the
        firmware even when the queue is paused - which it is during an
        active alarm. If the panel sends a queued JOG-IDLE while the queue
        is paused, the IDLE sits unexecuted and the arm keeps moving
        forever. Immediate frames bypass the queue entirely.
        """
        return self.write_command(CommandID.SET_JOG_CMD, pack_u8(int(mode), int(cmd)))

    def jog_stop(self) -> None:
        """Stop any active JOG. Best-effort: retries once on transport error
        because a stuck jog is a safety hazard."""
        try:
            self.jog(JOGCmd.IDLE)
        except (DobotConnectionError, DobotTimeoutError):
            # One retry - the arm is still moving and we MUST stop it.
            try:
                self.jog(JOGCmd.IDLE)
            except Exception:
                pass

    # ---- Queue control ------------------------------------------------
    def start_queue(self) -> None:
        self.write_command(CommandID.SET_QUEUED_CMD_START_EXEC)

    def stop_queue(self) -> None:
        self.write_command(CommandID.SET_QUEUED_CMD_STOP_EXEC)

    def force_stop_queue(self) -> None:
        self.write_command(CommandID.SET_QUEUED_CMD_FORCE_STOP_EXEC)

    def clear_queue(self) -> None:
        self.write_command(CommandID.SET_QUEUED_CMD_CLEAR)
        with self._index_lock:
            self._last_queued_index = 0

    def queued_cmd_current_index(self) -> int:
        frame = self.read_command(CommandID.GET_QUEUED_CMD_CURRENT_INDEX)
        return unpack_u64(frame.params)

    def queued_cmd_left_space(self) -> int:
        frame = self.read_command(CommandID.GET_QUEUED_CMD_LEFT_SPACE)
        return struct.unpack("<I", frame.params[:4])[0]

    def wait_for(
        self,
        index: int,
        *,
        timeout: float | None = None,
        poll: float = 0.02,
        raise_on_alarm: bool = True,
    ) -> None:
        """Block until the firmware queue has executed up through ``index``.

        ``raise_on_alarm`` (default ``True``): while waiting, also check
        :meth:`get_alarms`. If any motion-failure alarm bit fires
        (workspace / IK / joint-limit / singularity), raise
        :class:`DobotKinematicError` immediately instead of waiting forever
        for a command the firmware has refused to plan.
        """
        deadline = time.monotonic() + timeout if timeout is not None else None
        while True:
            current = self.queued_cmd_current_index()
            if raise_on_alarm:
                active = self.get_alarms()
                # Any alarm bit in the motion-related byte ranges (planning,
                # kinematic, over-speed, joint-limit, lost-step, other -
                # codes 0x10..0x77) means the firmware refused or aborted a
                # motion. Includes named codes AND unmapped bits in those
                # bands so an unknown joint-limit on a firmware variant
                # still surfaces as a DobotKinematicError.
                bad = [
                    (int(a), name, line)
                    for a, name, line in zip(
                        active.alarms, active.names(), active.format(), strict=True
                    )
                    if 0x10 <= int(a) <= 0x77
                ]
                if bad:
                    motion_alarm_names = [name for _, name, _ in bad]
                    bad_lines = [line for _, _, line in bad]
                    message = (
                        "motion failed:\n  - "
                        + "\n  - ".join(bad_lines)
                        + "\nRecover by calling clear_alarm() (or set_home() "
                        "if you want to also re-zero the arm) before retrying."
                    )
                    raise DobotKinematicError(alarms=motion_alarm_names, message=message)
            if current >= index:
                return
            if deadline is not None and time.monotonic() >= deadline:
                raise DobotTimeoutError(
                    f"queued cmd {index} not reached within {timeout}s (currently at {current})"
                )
            time.sleep(poll)

    def wait_idle(
        self,
        *,
        timeout: float | None = None,
        poll: float = 0.02,
        raise_on_alarm: bool = True,
    ) -> None:
        with self._index_lock:
            target = self._last_queued_index
        if target:
            self.wait_for(target, timeout=timeout, poll=poll, raise_on_alarm=raise_on_alarm)

    def batch(self):
        """Lazy run: pause the firmware queue, accumulate moves inside the
        block, resume execution on exit. DobotLab itself doesn't expose
        this idiom; it lets you queue an entire drawing first, then run it
        as a single continuous program at full motion-planning speed."""
        return batch_context(self)

    # ---- Real-time pose stream ----------------------------------------
    def start_pose_stream(
        self,
        callback: Callable[[Pose], None] | Queue | None = None,
        *,
        hz: float = 50.0,
    ) -> Queue:
        if self._pose_stream_thread is not None and self._pose_stream_thread.is_alive():
            raise RuntimeError("pose stream already running")
        if callback is None:
            callback = Queue()
        if isinstance(callback, Queue):
            sink: Queue = callback
            push: Callable[[Pose], None] = sink.put
        else:
            sink = Queue()
            push = callback
        period = max(0.0, 1.0 / max(hz, 1e-6))
        stop = threading.Event()
        self._pose_stream_stop = stop

        def stream_poses() -> None:
            next_sample_time = time.monotonic()
            while not stop.is_set():
                try:
                    push(self.get_pose())
                except Exception:
                    pass
                next_sample_time += period
                sleep_seconds = next_sample_time - time.monotonic()
                if sleep_seconds > 0:
                    stop.wait(sleep_seconds)
                else:
                    next_sample_time = time.monotonic()

        thread = threading.Thread(
            target=stream_poses,
            name=f"dobot-pose@{self.port or 'pending'}",
            daemon=True,
        )
        self._pose_stream_thread = thread
        thread.start()
        return callback if isinstance(callback, Queue) else sink

    def stop_pose_stream(self) -> None:
        if self._pose_stream_stop is not None:
            self._pose_stream_stop.set()
        if self._pose_stream_thread is not None:
            self._pose_stream_thread.join(timeout=1.0)
        self._pose_stream_stop = None
        self._pose_stream_thread = None

    # ---- Misc helpers -------------------------------------------------
    def get_device_serial_number(self) -> str:
        frame = self.read_command(CommandID.GET_DEVICE_SN)
        return frame.params.rstrip(b"\x00").decode("ascii", errors="replace")

    def get_device_name(self) -> str:
        frame = self.read_command(CommandID.GET_SET_DEVICE_NAME)
        return frame.params.rstrip(b"\x00").decode("ascii", errors="replace")

    def set_device_name(self, name: str) -> None:
        payload = name.encode("ascii") + b"\x00"
        self.write_command(CommandID.GET_SET_DEVICE_NAME, payload)

    def get_device_version(self) -> tuple[int, int, int]:
        frame = self.read_command(CommandID.GET_DEVICE_VERSION)
        major, minor, revision = frame.params[0], frame.params[1], frame.params[2]
        return major, minor, revision

    # ==================================================================
    # Backwards-compat aliases (older names this library used pre-3.6.x
    # alignment). Marked deprecated in their docstrings; safe to delete in
    # a future major release.
    # ==================================================================

    def home(self, **kwargs):
        """Deprecated alias for :meth:`set_home`."""
        return self.set_home(**kwargs)

    def clear_alarms(self) -> None:
        """Deprecated alias for :meth:`clear_alarm`."""
        self.clear_alarm()

    def wait_seconds(self, seconds: float) -> int:
        """Deprecated alias for :meth:`wait`."""
        return self.wait(seconds)

    def get_pose_l(self) -> float:
        """Deprecated alias for :meth:`get_posel`."""
        return self.get_posel()

    def get_slideway_pose(self) -> float:
        """Deprecated alias for :meth:`get_posel`."""
        return self.get_posel()


# Backwards-compat alias. The library was originally written with a
# generic ``Dobot`` name; it has been renamed to ``Magician`` to make
# room for other Dobot models. Old code keeps working unchanged.
Dobot = Magician

__all__ = ["Magician", "Dobot", "Pose"]
