"""Length-prefixed TCP messages shared by the broker and its clients."""

from __future__ import annotations

import socket
import struct

from .errors import DobotConnectionError, DobotError, DobotProtocolError, DobotTimeoutError

MIN_FRAME_BYTES = 6
MAX_FRAME_BYTES = 259  # header (2), length (1), payload (255), checksum (1)

ERROR_REPLY_LENGTH = 0

ERROR_TIMEOUT = 1  # the arm did not answer in time (the connection stays usable)
ERROR_CONNECTION = 2  # the serial link to the arm failed
ERROR_PROTOCOL = 3  # the request, or the arm's answer, was malformed
ERROR_INTERNAL = 4  # unexpected failure inside the broker

_ERROR_TYPES: dict[int, type[DobotError]] = {
    ERROR_TIMEOUT: DobotTimeoutError,
    ERROR_CONNECTION: DobotConnectionError,
    ERROR_PROTOCOL: DobotProtocolError,
    ERROR_INTERNAL: DobotConnectionError,
}


def error_code_for(error: Exception) -> int:
    """Map an exception raised while serving a request to its wire error code."""
    if isinstance(error, DobotTimeoutError):
        return ERROR_TIMEOUT
    if isinstance(error, DobotProtocolError):
        return ERROR_PROTOCOL
    if isinstance(error, DobotConnectionError):
        return ERROR_CONNECTION
    return ERROR_INTERNAL


def receive_exactly(connection: socket.socket, byte_count: int) -> bytes:
    """Read the requested bytes, including when TCP splits them across reads."""
    received = bytearray()
    while len(received) < byte_count:
        chunk = connection.recv(byte_count - len(received))
        if not chunk:
            raise ConnectionError("broker connection closed mid-message")
        received.extend(chunk)
    return bytes(received)


def send_frame_bytes(connection: socket.socket, frame_bytes: bytes) -> None:
    """Send a Dobot frame with its two-byte network-order length prefix."""
    connection.sendall(struct.pack("!H", len(frame_bytes)) + frame_bytes)


def send_error_reply(connection: socket.socket, code: int, message: str) -> None:
    """Tell the client its request failed, and why."""
    message_bytes = message.encode("utf-8", errors="replace")[:255]
    connection.sendall(
        struct.pack("!HBB", ERROR_REPLY_LENGTH, code, len(message_bytes)) + message_bytes
    )


def receive_frame_bytes(
    connection: socket.socket,
    *,
    wait_forever: bool = False,
    allow_error_reply: bool = False,
) -> bytes:
    """Read one framed message and reject lengths outside the Dobot format.

    With ``wait_forever`` the *first* bytes of the frame may take arbitrarily
    long (an idle client between requests). The connection's normal timeout
    still applies once a frame has started arriving.

    With ``allow_error_reply`` (clients reading the broker's answer) an error
    reply is raised as the matching :class:`DobotError` instead of being
    rejected as an invalid length.
    """
    if wait_forever:
        frame_timeout = connection.gettimeout()
        connection.settimeout(None)
        try:
            header = receive_exactly(connection, 1)
        finally:
            connection.settimeout(frame_timeout)
        header += receive_exactly(connection, 1)

    else:
        header = receive_exactly(connection, 2)

    frame_length = struct.unpack("!H", header)[0]
    if allow_error_reply and frame_length == ERROR_REPLY_LENGTH:
        code, message_length = receive_exactly(connection, 2)
        message = receive_exactly(connection, message_length).decode("utf-8", errors="replace")
        raise _ERROR_TYPES.get(code, DobotConnectionError)(message)

    if not MIN_FRAME_BYTES <= frame_length <= MAX_FRAME_BYTES:
        raise DobotProtocolError(f"invalid broker frame length: {frame_length}")

    return receive_exactly(connection, frame_length)
