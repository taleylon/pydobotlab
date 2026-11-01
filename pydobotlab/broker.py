"""TCP broker that lets several clients share one Dobot serial port.

:class:`DobotBroker` owns the serial transports and relays raw Dobot frames
between them and any number of local TCP clients, one request at a time per
port. The wire protocol is described in ``docs/panel/broker.md``.
"""

from __future__ import annotations

import socket
import socketserver
import threading
import time
from contextlib import closing

from .broker_protocol import (
    error_code_for,
    receive_exactly,
    receive_frame_bytes,
    send_error_reply,
    send_frame_bytes,
)
from .config import get_config
from .errors import (
    DobotConnectionError,
    DobotPermissionError,
    DobotPortInUseError,
    DobotProtocolError,
)
from .protocol import Frame, pack, unpack
from .transport import SerialTransport

# Handshake command bytes
CMD_LIST_PORTS = 0x00
CMD_ATTACH = 0x01

# Handshake reply bytes
REPLY_OK = 0x00
REPLY_NOTFOUND = 0x01
REPLY_BUSY = 0x02
REPLY_BAD_CMD = 0x03
REPLY_PERMISSION = 0x04


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

    ``host`` and ``port`` default to the configured values.
    """

    def __init__(self, host: str | None = None, port: int | None = None) -> None:
        settings = get_config()["broker"]
        self.host = settings["host"] if host is None else host
        self.port = settings["port"] if port is None else port
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
        # Open client connections, so that stop() can hang up on them.
        self._connections: set[socket.socket] = set()
        self._connections_lock = threading.Lock()
        self._server: socketserver.TCPServer | None = None
        self._server_thread: threading.Thread | None = None

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        if self._server is not None:
            return
        broker = self  # capture for handler closure

        class ClientHandler(socketserver.BaseRequestHandler):
            def handle(handler) -> None:
                with broker._connections_lock:
                    broker._connections.add(handler.request)
                try:
                    broker._handle_client(handler.request)
                finally:
                    with broker._connections_lock:
                        broker._connections.discard(handler.request)

        # ThreadingTCPServer so each client gets its own thread.
        class BrokerServer(socketserver.ThreadingTCPServer):
            daemon_threads = True
            allow_reuse_address = True
            # Do not wait for client threads on close, stop() hangs up on clients instead.
            block_on_close = False

        self._server = BrokerServer((self.host, self.port), ClientHandler)
        self.port = self._server.server_address[1]
        with _BROKER_CACHE_LOCK:
            _BROKER_CACHE.clear()  # a "no broker" answer from before the start is wrong
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
        # Hang up on connected clients: their next request fails at once.
        with self._connections_lock:
            connections = list(self._connections)
        for connection in connections:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
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
        self,
        port: str,
        *,
        baudrate: int | None = None,
        timeout: float | None = None,
        _lazy: bool = False,
    ) -> SerialTransport:
        """Open ``port`` and put it under broker management.

        ``baudrate`` and ``timeout`` default to the configured values.
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

    def client_count(self) -> int:
        """Number of clients connected to an arm through the broker."""
        with self._transports_lock:
            return sum(self._client_counts.values())

    # -- client handling -----------------------------------------------------

    def _handle_client(self, connection: socket.socket) -> None:
        settings = get_config()["broker"]
        connection.settimeout(settings["handshake_timeout"])
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
            except DobotConnectionError as error:
                if isinstance(error, DobotPermissionError):
                    failure_reply = REPLY_PERMISSION
                elif isinstance(error, DobotPortInUseError):
                    failure_reply = REPLY_BUSY
                else:
                    failure_reply = REPLY_NOTFOUND
                try:
                    connection.sendall(bytes([failure_reply]))
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

        # Frame relay loop. A client may sit idle between requests for as long
        # as it likes (a script waiting on input, a server waiting for
        # requests), so only a frame already under way is subject to
        # the frame timeout. TCP keepalive still reaps clients that vanished
        # without closing the socket.
        connection.settimeout(settings["frame_timeout"])
        connection.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        try:
            while True:
                try:
                    frame_bytes = receive_frame_bytes(connection, wait_forever=True)
                except DobotProtocolError as error:
                    # The byte stream is out of step, so say why and hang up.
                    self._reply_error(connection, error)
                    return
                except (TimeoutError, ConnectionError, OSError):
                    return  # client went away or stalled mid-frame
                # Every failure past this point is reported to the client as
                # an error reply - never swallowed - and the connection stays
                # open so the client decides whether to retry.
                try:
                    request = unpack(frame_bytes)
                    response: Frame = transport.send_frame(
                        request.cmd_id, request.ctrl, request.params
                    )
                    reply = pack(response.cmd_id, response.ctrl, response.params)
                except Exception as error:
                    garbled_reply = isinstance(error.__cause__, DobotProtocolError)
                    if isinstance(error, DobotConnectionError) and not garbled_reply:
                        self._drop_failed_transport(port_name, transport)
                    if not self._reply_error(connection, error):
                        return
                    continue
                try:
                    send_frame_bytes(connection, reply)
                except OSError:
                    return
        finally:
            # Decrement client count. If we lazily attached and we're the
            # last client out, close the SerialTransport so the OS releases
            # the port - otherwise a panel close would leave the broker
            # holding the port forever.
            self._release_client(port_name)

    def _drop_failed_transport(self, port: str, transport: SerialTransport) -> None:
        """Close a port whose serial link failed, for example when the arm was
        switched off, so the OS can give the arm the same port name when it
        comes back. The next client to attach opens the port again."""
        with self._transports_lock:
            if self._transports.get(port) is transport:
                del self._transports[port]
        transport.close()

    @staticmethod
    def _reply_error(connection: socket.socket, error: Exception) -> bool:
        """Send ``error`` to the client; ``False`` if the client is gone."""
        message = str(error) or type(error).__name__
        try:
            send_error_reply(connection, error_code_for(error), message)
        except OSError:
            return False
        return True

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


def is_broker_reachable(
    host: str | None = None,
    port: int | None = None,
    timeout: float | None = None,
) -> bool:
    """``True`` iff a :class:`DobotBroker` is accepting connections.

    Arguments default to the configured values. A result is reused for a
    short time.
    """
    settings = get_config()["broker"]
    host = settings["host"] if host is None else host
    port = settings["port"] if port is None else port
    timeout = settings["probe_timeout"] if timeout is None else timeout
    key = (host, port)
    now = time.monotonic()
    with _BROKER_CACHE_LOCK:
        cached = _BROKER_CACHE.get(key)
        if cached is not None and now - cached[0] < settings["probe_cache_seconds"]:
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
    host: str | None = None,
    port: int | None = None,
    timeout: float | None = None,
) -> list[str]:
    """Ask the broker which ports it currently has attached.

    Arguments default to the configured values.
    """
    settings = get_config()["broker"]
    host = settings["host"] if host is None else host
    port = settings["port"] if port is None else port
    timeout = settings["handshake_timeout"] if timeout is None else timeout
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
