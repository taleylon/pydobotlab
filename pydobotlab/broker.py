"""TCP broker for the Dobot Magician serial port.

Why a broker?
-------------

A serial port can only be opened by one process at a time. That means a
control-panel GUI and a Python script in PyCharm can't both talk to the
same arm - one of them gets a "port busy" error. DobotStudio works around
this with its **DobotLink** helper: a local daemon that owns the port and
multiplexes traffic for everything else.

This module is the equivalent for pydobotlab. When ``pydobotlab-panel`` runs,
it boots a :class:`DobotBroker` on ``127.0.0.1:DEFAULT_BROKER_PORT``. The
broker:

* Owns the underlying :class:`~pydobotlab.transport.SerialTransport` for each
  port that's been attached.
* Accepts TCP connections from any number of in-process or out-of-process
  clients (the panel itself, students' PyCharm scripts, Jupyter notebooks).
* Serializes their requests through one per-port lock so frames can't
  interleave on the wire.
* Localhost-bind only; never accepts remote connections.

Wire protocol (intentionally minimal, framed in the protocol layer
already):

    Handshake (one-shot, after connect):
        client -> server:  0x01 PORT_LEN PORT_BYTES        (ATTACH cmd)
                  or:      0x00                            (LIST_PORTS cmd)
        server -> client:  0x00 (ok)  | 0x01 PORT (not_found, ATTACH)
                  or:      N=u8 + (u8 len + bytes)*N       (LIST_PORTS reply)

    After successful ATTACH, the connection is in "frame relay" mode:
        client -> server:  u16-be length + raw Dobot frame
        server -> client:  u16-be length + raw Dobot frame

The "raw Dobot frame" is exactly what :func:`pydobotlab.protocol.pack`
produces - header, len, ID, ctrl, params, checksum.
"""

from __future__ import annotations

import socket
import socketserver
import threading
import time
from contextlib import closing

from .broker_protocol import receive_exactly, receive_frame_bytes, send_frame_bytes
from .errors import DobotConnectionError, DobotProtocolError, DobotTimeoutError
from .protocol import Frame, pack, unpack
from .transport import SerialTransport

DEFAULT_BROKER_HOST = "127.0.0.1"
DEFAULT_BROKER_PORT = 8765
DEFAULT_PROBE_TIMEOUT = 0.15  # seconds, for `is_broker_reachable`
HANDSHAKE_TIMEOUT = 1.0
FRAME_TIMEOUT = 5.0

# Handshake command bytes
CMD_LIST_PORTS = 0x00
CMD_ATTACH = 0x01

# Handshake reply bytes
REPLY_OK = 0x00
REPLY_NOTFOUND = 0x01
REPLY_BUSY = 0x02
REPLY_BAD_CMD = 0x03


# ---------------------------------------------------------------------------
# Broker server
# ---------------------------------------------------------------------------


class DobotBroker:
    """Run a small TCP broker that owns one or more SerialTransports.

    Use as a context manager from the GUI process::

        with DobotBroker() as broker:
            broker.attach("/dev/ttyUSB0")
            ...

    Or just ``broker.start()`` / ``broker.stop()``.
    """

    def __init__(
        self,
        host: str = DEFAULT_BROKER_HOST,
        port: int = DEFAULT_BROKER_PORT,
    ) -> None:
        self.host = host
        self.port = port
        self._transports: dict[str, SerialTransport] = {}
        # Per-port reference counts: how many TCP clients currently hold an
        # ATTACH on this port. We auto-detach lazily-attached ports when the
        # last client disconnects, so closing the panel really does release
        # the serial port (otherwise the next discovery probe would see the
        # port as "claimed" by the broker's still-open SerialTransport).
        self._client_counts: dict[str, int] = {}
        # Ports the broker opened on demand (vs. attached up-front by the
        # GUI process). Only these are auto-detached when count hits 0.
        self._lazy_attached: set[str] = set()
        self._transports_lock = threading.Lock()
        self._server: socketserver.TCPServer | None = None
        self._server_thread: threading.Thread | None = None

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        if self._server is not None:
            return
        broker = self  # capture for handler closure

        class ClientHandler(socketserver.BaseRequestHandler):
            def handle(handler) -> None:
                broker._handle_client(handler.request)

        # ThreadingTCPServer so each client gets its own thread.
        class BrokerServer(socketserver.ThreadingTCPServer):
            daemon_threads = True
            allow_reuse_address = True

        self._server = BrokerServer((self.host, self.port), ClientHandler)
        self.port = self._server.server_address[1]
        self._server_thread = threading.Thread(
            target=self._server.serve_forever,
            name=f"dobot-broker@{self.host}:{self.port}",
            daemon=True,
        )
        self._server_thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._server_thread is not None:
            self._server_thread.join(timeout=2.0)
            self._server_thread = None
        with self._transports_lock:
            for transport in self._transports.values():
                try:
                    transport.close()
                except Exception:
                    pass
            self._transports.clear()

    def __enter__(self) -> DobotBroker:
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()

    # -- transport ownership -------------------------------------------------

    def attach(
        self, port: str, *, baudrate: int = 115200, timeout: float = 1.0, _lazy: bool = False
    ) -> SerialTransport:
        """Open ``port`` and put it under broker management.

        If already attached, returns the existing transport. Pass
        ``_lazy=True`` (used by the TCP handler when a client requests a
        previously-unattached port) to mark the attach as auto-detachable
        when the last client disconnects.
        """
        with self._transports_lock:
            if port in self._transports:
                return self._transports[port]
            transport = SerialTransport(port, baudrate=baudrate, timeout=timeout)
            transport.open()
            self._transports[port] = transport
            if _lazy:
                self._lazy_attached.add(port)
            return transport

    def detach(self, port: str) -> None:
        with self._transports_lock:
            transport = self._transports.pop(port, None)
        if transport is not None:
            try:
                transport.close()
            except Exception:
                pass

    def attached_ports(self) -> list[str]:
        with self._transports_lock:
            return sorted(self._transports.keys())

    # -- client handling -----------------------------------------------------

    def _handle_client(self, connection: socket.socket) -> None:
        connection.settimeout(HANDSHAKE_TIMEOUT)
        try:
            command = receive_exactly(connection, 1)[0]
        except (TimeoutError, ConnectionError, OSError):
            return

        if command == CMD_LIST_PORTS:
            self._reply_list_ports(connection)
            return

        if command != CMD_ATTACH:
            try:
                connection.sendall(bytes([REPLY_BAD_CMD]))
            except OSError:
                pass
            return

        # ATTACH: read port name
        try:
            name_length = receive_exactly(connection, 1)[0]
            port_name = receive_exactly(connection, name_length).decode("ascii", errors="replace")
        except (TimeoutError, ConnectionError, OSError):
            return

        with self._transports_lock:
            transport = self._transports.get(port_name)
        attached_for_this_client = False
        if transport is None:
            try:
                transport = self.attach(port_name, _lazy=True)
            except DobotConnectionError:
                try:
                    connection.sendall(bytes([REPLY_NOTFOUND]))
                except Exception:
                    pass
                return
            attached_for_this_client = True

        try:
            connection.sendall(bytes([REPLY_OK]))
        except Exception:
            if attached_for_this_client:
                self._release_client(port_name)
            return

        # Bump client-count NOW that ATTACH succeeded.
        with self._transports_lock:
            self._client_counts[port_name] = self._client_counts.get(port_name, 0) + 1

        # Frame relay loop
        connection.settimeout(FRAME_TIMEOUT)
        try:
            while True:
                try:
                    frame_bytes = receive_frame_bytes(connection)
                except (TimeoutError, ConnectionError, OSError, DobotProtocolError):
                    return
                try:
                    request = unpack(frame_bytes)
                    response: Frame = transport.send_frame(
                        request.cmd_id, request.ctrl, request.params
                    )
                    send_frame_bytes(
                        connection, pack(response.cmd_id, response.ctrl, response.params)
                    )
                except DobotTimeoutError:
                    return
                except Exception:
                    return
        finally:
            # Decrement client count. If we lazily attached and we're the
            # last client out, close the SerialTransport so the OS releases
            # the port - otherwise a panel close would leave the broker
            # holding the port forever.
            self._release_client(port_name)

    def _release_client(self, port: str) -> None:
        """Decrement ref count; detach if zero clients remain on a lazy port."""
        with self._transports_lock:
            client_count = self._client_counts.get(port, 0) - 1
            if client_count > 0:
                self._client_counts[port] = client_count
                return
            self._client_counts.pop(port, None)
            should_detach = port in self._lazy_attached
            if should_detach:
                self._lazy_attached.discard(port)
        if should_detach:
            self.detach(port)

    def _reply_list_ports(self, connection: socket.socket) -> None:
        with self._transports_lock:
            ports = sorted(self._transports.keys())
        response = bytearray([len(ports) & 0xFF])
        for port in ports:
            data = port.encode("ascii", errors="replace")[:255]
            response.append(len(data))
            response += data
        try:
            connection.sendall(bytes(response))
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Probe helpers (used by Dobot() auto-detect)
# ---------------------------------------------------------------------------

# Per-process cache: True/False/None ("not yet probed"). We re-probe rarely
# because opening a TCP connection is cheap but not free, and a fresh probe
# every Dobot() construction would slow scripts noticeably.
_BROKER_CACHE_LOCK = threading.Lock()
_BROKER_CACHE: dict[tuple[str, int], tuple[float, bool]] = {}
_BROKER_CACHE_TTL = 2.0


def is_broker_reachable(
    host: str = DEFAULT_BROKER_HOST,
    port: int = DEFAULT_BROKER_PORT,
    timeout: float = DEFAULT_PROBE_TIMEOUT,
) -> bool:
    """``True`` iff a :class:`DobotBroker` is accepting connections."""
    key = (host, port)
    now = time.monotonic()
    with _BROKER_CACHE_LOCK:
        cached = _BROKER_CACHE.get(key)
        if cached is not None and now - cached[0] < _BROKER_CACHE_TTL:
            return cached[1]

    reachable = False
    try:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as connection:
            connection.settimeout(timeout)
            connection.connect((host, port))
            reachable = True
    except OSError:
        reachable = False

    with _BROKER_CACHE_LOCK:
        _BROKER_CACHE[key] = (now, reachable)
    return reachable


def list_broker_ports(
    host: str = DEFAULT_BROKER_HOST,
    port: int = DEFAULT_BROKER_PORT,
    timeout: float = HANDSHAKE_TIMEOUT,
) -> list[str]:
    """Ask the broker which ports it currently has attached."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as connection:
        connection.settimeout(timeout)
        connection.connect((host, port))
        connection.sendall(bytes([CMD_LIST_PORTS]))
        port_count = receive_exactly(connection, 1)[0]
        response: list[str] = []
        for _ in range(port_count):
            name_length = receive_exactly(connection, 1)[0]
            response.append(
                receive_exactly(connection, name_length).decode("ascii", errors="replace")
            )
        return response
