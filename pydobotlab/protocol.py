"""Wire-level framing for the Dobot Magician communication protocol.

Frame layout (little-endian, multi-byte fields):

::

    +--------+--------+--------+--------+--------+--- ... ---+----------+
    |  0xAA  |  0xAA  |  len   |   ID   |  Ctrl  |  Params   | Checksum |
    +--------+--------+--------+--------+--------+--- ... ---+----------+
              header           |<----- "payload" of `len` bytes ----->|

* ``len`` counts ``ID`` + ``Ctrl`` + ``Params`` (excludes header and checksum).
* ``Ctrl`` bit 0  = rw       (0 = read / get,  1 = write / set)
* ``Ctrl`` bit 1  = isQueued (0 = run now,     1 = enqueue in firmware queue)
* ``Checksum`` is the byte that makes ``(sum(payload) + checksum) % 256 == 0``,
  i.e. ``checksum = (-sum(payload)) & 0xFF``.

When ``isQueued`` is set on a ``set`` command, the response payload contains a
single ``uint64`` queued-command index instead of the usual command-specific
data.
"""

from __future__ import annotations

import struct
from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum

from .errors import DobotProtocolError

HEADER = b"\xaa\xaa"

# Control byte bits
CTRL_RW = 0b01  # 1 = write/set, 0 = read/get
CTRL_QUEUED = 0b10  # 1 = enqueue, 0 = immediate


# ---------------------------------------------------------------------------
# Mode enums shared between the protocol and the high-level API.
# ---------------------------------------------------------------------------


class PTPMode(IntEnum):
    """Modes for ``SetPTPCmd`` (cmd ID 84)."""

    JUMP_XYZ = 0  # jump (lift, move, drop) to Cartesian (x, y, z, r)
    MOVJ_XYZ = 1  # joint-interpolated move to Cartesian (x, y, z, r)
    MOVL_XYZ = 2  # linear move to Cartesian (x, y, z, r)
    JUMP_ANGLE = 3  # jump to joint angles (j1, j2, j3, j4)
    MOVJ_ANGLE = 4  # joint-interpolated move to joint angles
    MOVL_ANGLE = 5  # linear (in joint space) move to joint angles
    MOVJ_INC = 6  # relative joint move (delta j1..j4)
    MOVL_INC = 7  # relative Cartesian linear move (delta x, y, z, r)
    MOVJ_XYZ_INC = 8  # relative Cartesian joint-interpolated move


class JogMode(IntEnum):
    """``isJoint`` selector for ``SetJOGCmd``."""

    COORDINATE = 0
    JOINT = 1


class JOGCmd(IntEnum):
    """``cmd`` selector for ``SetJOGCmd`` (cmd ID 73)."""

    IDLE = 0
    AP_DOWN = 1  # axis 1 +  (X+ in coord, J1+ in joint)
    AN_DOWN = 2  # axis 1 -
    BP_DOWN = 3  # axis 2 +  (Y+ / J2+)
    BN_DOWN = 4  # axis 2 -
    CP_DOWN = 5  # axis 3 +  (Z+ / J3+)
    CN_DOWN = 6  # axis 3 -
    DP_DOWN = 7  # axis 4 +  (R+ / J4+)
    DN_DOWN = 8  # axis 4 -


class EndEffectorType(IntEnum):
    """Identifier returned by ``GetEndEffectorParams``."""

    LASER = 0
    SUCTION_CUP = 1
    GRIPPER = 2


class IOFunction(IntEnum):
    """``IOFunction`` for ``SetIOMultiplexing`` (cmd ID 130)."""

    DUMMY = 0
    DO = 1
    PWM = 2
    DI = 3
    ADC = 4
    DIPU = 5  # DI pull-up
    DIPD = 6  # DI pull-down


# ---------------------------------------------------------------------------
# Frame pack / unpack
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Frame:
    """A decoded Dobot protocol frame."""

    cmd_id: int
    ctrl: int
    params: bytes

    @property
    def rw(self) -> bool:
        return bool(self.ctrl & CTRL_RW)

    @property
    def is_queued(self) -> bool:
        return bool(self.ctrl & CTRL_QUEUED)


def calculate_checksum(payload: bytes) -> int:
    """Return the byte that makes the payload sum zero modulo 256."""
    return (-sum(payload)) & 0xFF


def pack(cmd_id: int, ctrl: int, params: bytes = b"") -> bytes:
    """Serialize a frame to bytes ready for the wire."""
    if not 0 <= cmd_id <= 0xFF:
        raise ValueError(f"cmd_id out of range: {cmd_id}")
    if not 0 <= ctrl <= 0xFF:
        raise ValueError(f"ctrl out of range: {ctrl}")
    payload_length = 2 + len(params)  # id + ctrl + params
    if payload_length > 0xFF:
        raise ValueError(f"params too long: {len(params)} bytes")
    payload = bytes((cmd_id, ctrl)) + params
    return HEADER + bytes((payload_length,)) + payload + bytes((calculate_checksum(payload),))


def unpack(frame_bytes: bytes) -> Frame:
    """Parse a complete frame from ``buf``. Raises :class:`DobotProtocolError`."""
    if len(frame_bytes) < 6:
        raise DobotProtocolError(f"frame too short: {len(frame_bytes)} bytes")
    if frame_bytes[0:2] != HEADER:
        raise DobotProtocolError(f"bad header: {frame_bytes[0:2]!r}")
    payload_length = frame_bytes[2]
    if payload_length < 2:
        raise DobotProtocolError(f"payload too short: {payload_length} bytes")
    expected_length = 3 + payload_length + 1
    if len(frame_bytes) != expected_length:
        raise DobotProtocolError(
            f"bad frame length: expected {expected_length}, got {len(frame_bytes)}"
        )
    payload = frame_bytes[3 : 3 + payload_length]
    checksum = frame_bytes[-1]
    if (sum(payload) + checksum) & 0xFF != 0:
        raise DobotProtocolError(f"checksum mismatch: payload={payload.hex()} chk=0x{checksum:02x}")
    return Frame(cmd_id=payload[0], ctrl=payload[1], params=bytes(payload[2:]))


def read_frame(read_byte: Callable[[], bytes]) -> Frame:
    """Read a frame from a callable that returns one byte (or empty on timeout).

    ``read_byte`` is invoked repeatedly until a complete, valid frame is
    assembled or it raises. The reader handles partial reads, junk bytes
    before the header, and raises on bad checksums.
    """
    # Find header (resync-tolerant)
    state = 0  # 0 = looking for first 0xAA, 1 = looking for second
    while True:
        received_byte = read_byte()
        if not received_byte:
            raise DobotProtocolError("timeout waiting for frame header")
        byte = received_byte[0]
        if state == 0 and byte == 0xAA:
            state = 1
        elif state == 1 and byte == 0xAA:
            break
        elif state == 1:
            state = 0  # resync
        # else still 0, byte != 0xAA, keep scanning

    # Length
    received_byte = read_byte()
    if not received_byte:
        raise DobotProtocolError("timeout waiting for frame length")
    payload_length = received_byte[0]

    # Payload
    payload = bytearray()
    while len(payload) < payload_length:
        chunk = read_byte()
        if not chunk:
            raise DobotProtocolError("timeout reading frame payload")
        payload += chunk

    # Checksum
    received_byte = read_byte()
    if not received_byte:
        raise DobotProtocolError("timeout waiting for checksum")
    checksum = received_byte[0]

    if (sum(payload) + checksum) & 0xFF != 0:
        raise DobotProtocolError(
            f"checksum mismatch on incoming frame: {bytes(payload).hex()} chk=0x{checksum:02x}"
        )
    if payload_length < 2:
        raise DobotProtocolError(f"payload too short: {payload_length} bytes")
    return Frame(cmd_id=payload[0], ctrl=payload[1], params=bytes(payload[2:]))


# ---------------------------------------------------------------------------
# Convenience param packers — used by device.py to build typed commands.
# All multi-byte fields are little-endian per the protocol spec.
# ---------------------------------------------------------------------------


def pack_floats(*values: float) -> bytes:
    """Pack 32-bit little-endian IEEE-754 floats."""
    return struct.pack(f"<{len(values)}f", *values)


def unpack_floats(data: bytes) -> tuple[float, ...]:
    float_count, remainder = divmod(len(data), 4)
    if remainder:
        raise DobotProtocolError(f"float buffer not multiple of 4: {len(data)} bytes")
    return struct.unpack(f"<{float_count}f", data)


def pack_u8(*values: int) -> bytes:
    return bytes(values)


def pack_u16(*values: int) -> bytes:
    return struct.pack(f"<{len(values)}H", *values)


def pack_u32(*values: int) -> bytes:
    return struct.pack(f"<{len(values)}I", *values)


def pack_u64(value: int) -> bytes:
    return struct.pack("<Q", value)


def unpack_u64(data: bytes) -> int:
    if len(data) < 8:
        raise DobotProtocolError(f"need 8 bytes for u64, got {len(data)}")
    return struct.unpack("<Q", data[:8])[0]
