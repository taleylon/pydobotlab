"""Length-prefixed TCP messages shared by the broker and its clients."""

from __future__ import annotations

import socket
import struct

from .errors import DobotProtocolError

MIN_FRAME_BYTES = 6
MAX_FRAME_BYTES = 259  # header (2), length (1), payload (255), checksum (1)


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


def receive_frame_bytes(connection: socket.socket) -> bytes:
    """Read one framed message and reject lengths outside the Dobot format."""
    frame_length = struct.unpack("!H", receive_exactly(connection, 2))[0]
    if not MIN_FRAME_BYTES <= frame_length <= MAX_FRAME_BYTES:
        raise DobotProtocolError(f"invalid broker frame length: {frame_length}")
    return receive_exactly(connection, frame_length)
