"""Serial transport bound to a single Dobot.

The :class:`SerialTransport` opens a port, writes raw frame bytes, and
reads complete frames back. All of the protocol logic lives one layer up in
:mod:`pydobotlab.device`.

Each instance owns its own :class:`serial.Serial`, so multiple Dobots on the
same machine are completely independent.
"""

from __future__ import annotations

import socket
import threading

import serial

from .broker_protocol import receive_exactly, receive_frame_bytes, send_frame_bytes
from .errors import DobotConnectionError, DobotPortInUseError, DobotTimeoutError
from .protocol import Frame, pack, read_frame, unpack

DEFAULT_BAUDRATE = 115200
DEFAULT_TIMEOUT_S = 1.0


# ---------------------------------------------------------------------------
# Process-local port registry
#
# pyserial's ``exclusive=True`` covers cross-process collisions on POSIX, but
# *within* this Python process two ``Dobot(port=...)`` calls with the same
# argument can both ``open()`` the device successfully on some platforms.
# This registry catches that case eagerly so the second instance fails fast
# with a clean :class:`DobotPortInUseError` rather than weird interleaved I/O.
# ---------------------------------------------------------------------------

_REGISTRY_LOCK = threading.Lock()
_OPEN_PORTS: set[str] = set()


def is_port_claimed(port: str) -> bool:
    """``True`` iff ``port`` is currently held by a :class:`SerialTransport`."""
    with _REGISTRY_LOCK:
        return port in _OPEN_PORTS


def claimed_ports() -> list[str]:
    """Snapshot of ports currently held by this process."""
    with _REGISTRY_LOCK:
        return sorted(_OPEN_PORTS)


class SerialTransport:
    """A thread-safe wrapper around a single :class:`serial.Serial` port.

    The wrapper guarantees that a write/read pair for one frame is atomic
    relative to other concurrent users of this transport — so a worker thread
    can drive a request/response loop without interleaving traffic.

    Parameters
    ----------
    port:
        OS-specific serial device path (``/dev/ttyUSB0``, ``COM3``...).
    baudrate:
        Defaults to 115200 — the only baud rate the Magician firmware speaks.
    timeout:
        Per-byte read timeout, in seconds. Frame-level reads accumulate bytes
        and surface a :class:`DobotTimeoutError` if a full frame doesn't
        arrive in time.
    exclusive:
        On Linux, request an exclusive lock on the port (``flock``) so a
        second :class:`Dobot` instance can't accidentally grab the same arm.
    """

    def __init__(
        self,
        port: str,
        baudrate: int = DEFAULT_BAUDRATE,
        timeout: float = DEFAULT_TIMEOUT_S,
        *,
        exclusive: bool = True,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._exclusive = exclusive
        self._serial: serial.Serial | None = None
        self._lock = threading.Lock()

    # -- lifecycle -----------------------------------------------------------

    def open(self) -> None:
        if self._serial is not None and self._serial.is_open:
            return
        # 1. Refuse double-claims from this process (clean error, fast fail).
        with _REGISTRY_LOCK:
            if self.port in _OPEN_PORTS:
                raise DobotPortInUseError(
                    f"port {self.port!r} is already in use by another Dobot "
                    f"instance in this process"
                )
            _OPEN_PORTS.add(self.port)
        # 2. Open the underlying device.
        #
        # Construct the port CLOSED, set the control-line states, then open.
        # The Magician's STM32 controller wires DTR/RTS to its NRST/BOOT0 pins,
        # so pyserial's default of asserting both on open pulses the MCU into
        # its system bootloader - the arm stops answering the protocol and
        # only a power-cycle recovers it (DobotStudio then reports "invalid
        # device type"). Opening with both lines held low avoids that reset;
        # the CH340 bridge doesn't need them asserted to transmit/receive.
        serial_port = None
        try:
            serial_port = serial.Serial()
            serial_port.port = self.port
            serial_port.baudrate = self.baudrate
            serial_port.bytesize = serial.EIGHTBITS
            serial_port.parity = serial.PARITY_NONE
            serial_port.stopbits = serial.STOPBITS_ONE
            serial_port.timeout = self.timeout
            serial_port.write_timeout = self.timeout
            serial_port.dtr = False
            serial_port.rts = False
            try:
                serial_port.exclusive = self._exclusive
            except (ValueError, AttributeError, NotImplementedError):
                # `exclusive` unsupported on this platform / pyserial — ignore.
                pass
            serial_port.open()
            self._serial = serial_port
            self._serial.reset_input_buffer()
            self._serial.reset_output_buffer()
        except serial.SerialException as error:
            if serial_port is not None:
                try:
                    serial_port.close()
                except serial.SerialException:
                    pass
            self._serial = None
            with _REGISTRY_LOCK:
                _OPEN_PORTS.discard(self.port)
            message = str(error).lower()
            if (
                "could not exclusively lock" in message
                or "permission denied" in message
                or "device or resource busy" in message
            ):
                raise DobotPortInUseError(
                    f"port {self.port!r} is already in use by another process: {error}"
                ) from error
            raise DobotConnectionError(f"cannot open {self.port!r}: {error}") from error
        except Exception:
            if serial_port is not None:
                try:
                    serial_port.close()
                except serial.SerialException:
                    pass
            self._serial = None
            with _REGISTRY_LOCK:
                _OPEN_PORTS.discard(self.port)
            raise

    def close(self) -> None:
        with self._lock:
            if self._serial is not None and self._serial.is_open:
                try:
                    self._serial.close()
                except serial.SerialException:
                    pass
            self._serial = None
        with _REGISTRY_LOCK:
            _OPEN_PORTS.discard(self.port)

    @property
    def is_open(self) -> bool:
        return self._serial is not None and self._serial.is_open

    # -- frame I/O -----------------------------------------------------------

    def send_frame(self, cmd_id: int, ctrl: int, params: bytes = b"") -> Frame:
        if self._serial is None or not self._serial.is_open:
            raise DobotConnectionError(f"transport for {self.port!r} is not open")

        frame_bytes = pack(cmd_id, ctrl, params)

        with self._lock:
            try:
                self._serial.write(frame_bytes)
                self._serial.flush()
            except serial.SerialTimeoutException as error:
                raise DobotTimeoutError(f"write timeout on {self.port!r}") from error
            except serial.SerialException as error:
                raise DobotConnectionError(f"write failed on {self.port!r}: {error}") from error

            try:
                return read_frame(self._read_byte)
            except DobotTimeoutError:
                raise
            except Exception as error:
                raise DobotConnectionError(f"read failed on {self.port!r}: {error}") from error

    def _read_byte(self) -> bytes:
        assert self._serial is not None
        data = self._serial.read(1)
        if not data:
            raise DobotTimeoutError(f"read timeout on {self.port!r}")
        return data


# ---------------------------------------------------------------------------
# BrokerTransport — TCP-backed transport used when a DobotBroker is running.
#
# Same public shape as SerialTransport so device.py can swap them blind.
# ---------------------------------------------------------------------------


class BrokerTransport:
    """Talks to a :class:`pydobotlab.broker.DobotBroker` over TCP.

    Used by :class:`Dobot` automatically when a broker is reachable; the
    student's code path is identical whether the panel is running (broker
    on) or not (direct serial).
    """

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,  # accepted for shape; ignored
        timeout: float = 1.0,
        *,
        broker_host: str = "127.0.0.1",
        broker_port: int = 8765,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._broker_host = broker_host
        self._broker_port = broker_port
        self._socket: socket.socket | None = None
        self._lock = threading.Lock()

    # -- lifecycle -----------------------------------------------------------

    def open(self) -> None:
        if self._socket is not None:
            return
        port_bytes = self.port.encode("ascii")
        if not 1 <= len(port_bytes) <= 255:
            raise ValueError("broker port name must contain 1..255 ASCII bytes")
        connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            connection.settimeout(2.0)
            connection.connect((self._broker_host, self._broker_port))
            connection.sendall(bytes((0x01, len(port_bytes))) + port_bytes)
            reply = receive_exactly(connection, 1)[0]
            if reply == 0x01:
                raise DobotConnectionError(f"broker could not open transport for {self.port!r}")
            if reply == 0x02:
                raise DobotPortInUseError(f"broker reports {self.port!r} is busy")
            if reply != 0x00:
                raise DobotConnectionError(f"broker handshake failed (reply 0x{reply:02x})")
            connection.settimeout(self.timeout + 5.0)
        except OSError as error:
            connection.close()
            raise DobotConnectionError(
                f"cannot connect to broker at {self._broker_host}:{self._broker_port}: {error}"
            ) from error
        except Exception:
            connection.close()
            raise
        self._socket = connection

    def close(self) -> None:
        with self._lock:
            if self._socket is not None:
                try:
                    self._socket.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                try:
                    self._socket.close()
                except OSError:
                    pass
                self._socket = None

    @property
    def is_open(self) -> bool:
        return self._socket is not None

    # -- frame I/O -----------------------------------------------------------

    def send_frame(self, cmd_id: int, ctrl: int, params: bytes = b"") -> Frame:
        frame_bytes = pack(cmd_id, ctrl, params)
        with self._lock:
            if self._socket is None:
                raise DobotConnectionError(f"broker transport for {self.port!r} is not open")
            try:
                send_frame_bytes(self._socket, frame_bytes)
                response = receive_frame_bytes(self._socket)
            except TimeoutError as error:
                raise DobotTimeoutError(f"broker timeout on {self.port!r}") from error
            except OSError as error:
                raise DobotConnectionError(f"broker I/O on {self.port!r}: {error}") from error
        return unpack(response)
