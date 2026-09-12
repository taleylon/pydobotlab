"""Hardware-free tests for the wire protocol.

Run with ``pytest`` from the package root. None of these tests require an
attached Dobot — they exercise the byte-level packer, unpacker, and reader.
"""

from __future__ import annotations

import io

import pytest

from pydobotlab.alarms import Alarm, decode_alarms, encode_alarms
from pydobotlab.commands import CommandID
from pydobotlab.errors import DobotProtocolError
from pydobotlab.protocol import (
    CTRL_QUEUED,
    CTRL_RW,
    HEADER,
    pack,
    pack_floats,
    read_frame,
    unpack,
    unpack_floats,
)

# ---------------------------------------------------------------------------
# pack / unpack round-trip
# ---------------------------------------------------------------------------


class TestPackUnpack:
    def test_empty_params_round_trip(self):
        wire = pack(CommandID.GET_POSE, 0)
        frame = unpack(wire)
        assert frame.cmd_id == CommandID.GET_POSE
        assert frame.ctrl == 0
        assert frame.params == b""

    def test_with_params_round_trip(self):
        params = pack_floats(100.0, 200.0, 50.0, 0.0)
        wire = pack(CommandID.SET_PTP_CMD, CTRL_RW | CTRL_QUEUED, b"\x01" + params)
        frame = unpack(wire)
        assert frame.cmd_id == CommandID.SET_PTP_CMD
        assert frame.rw is True
        assert frame.is_queued is True
        assert frame.params[0] == 1
        assert unpack_floats(frame.params[1:]) == (100.0, 200.0, 50.0, 0.0)

    def test_header_present(self):
        wire = pack(CommandID.GET_POSE, 0)
        assert wire[:2] == HEADER

    def test_length_field_excludes_header_and_checksum(self):
        # length byte = id + ctrl + params
        wire = pack(CommandID.SET_HOME_CMD, CTRL_RW | CTRL_QUEUED, b"\x00\x00\x00\x00")
        # 1 (id) + 1 (ctrl) + 4 (params) = 6
        assert wire[2] == 6

    def test_checksum_makes_payload_sum_zero(self):
        wire = pack(CommandID.SET_PTP_CMD, CTRL_RW, b"\x00" + pack_floats(1.0, 2.0, 3.0, 4.0))
        payload = wire[3:-1]
        chk = wire[-1]
        assert (sum(payload) + chk) % 256 == 0

    def test_unpack_rejects_bad_header(self):
        wire = bytearray(pack(CommandID.GET_POSE, 0))
        wire[0] = 0x55
        with pytest.raises(DobotProtocolError):
            unpack(bytes(wire))

    def test_unpack_rejects_bad_checksum(self):
        wire = bytearray(pack(CommandID.GET_POSE, 0))
        wire[-1] ^= 0x01
        with pytest.raises(DobotProtocolError):
            unpack(bytes(wire))

    def test_unpack_rejects_bad_length(self):
        wire = bytearray(pack(CommandID.GET_POSE, 0))
        wire[2] = 99
        with pytest.raises(DobotProtocolError):
            unpack(bytes(wire))


# ---------------------------------------------------------------------------
# read_frame: stream-based parser, tolerant to leading garbage
# ---------------------------------------------------------------------------


class _ByteStream:
    """Minimal helper that mimics SerialTransport._read_byte."""

    def __init__(self, data: bytes):
        self._buf = io.BytesIO(data)

    def __call__(self) -> bytes:
        return self._buf.read(1)


class TestReadFrame:
    def test_clean_frame(self):
        wire = pack(CommandID.GET_POSE, 0, b"")
        frame = read_frame(_ByteStream(wire))
        assert frame.cmd_id == CommandID.GET_POSE

    def test_resyncs_past_leading_junk(self):
        wire = b"\x55\x77\xaa\x99" + pack(CommandID.GET_POSE, 0, b"")
        frame = read_frame(_ByteStream(wire))
        assert frame.cmd_id == CommandID.GET_POSE

    def test_handles_partial_header(self):
        # Single 0xAA followed by other bytes should resync to next true header.
        wire = b"\xaa\x00" + pack(CommandID.GET_POSE, 0, b"")
        frame = read_frame(_ByteStream(wire))
        assert frame.cmd_id == CommandID.GET_POSE

    def test_raises_on_short_stream(self):
        wire = pack(CommandID.GET_POSE, 0, b"")[:5]
        with pytest.raises(DobotProtocolError):
            read_frame(_ByteStream(wire))

    def test_raises_on_corrupt_checksum(self):
        wire = bytearray(pack(CommandID.GET_POSE, 0, b""))
        wire[-1] ^= 0xFF
        with pytest.raises(DobotProtocolError):
            read_frame(_ByteStream(bytes(wire)))


# ---------------------------------------------------------------------------
# Alarm bitmask decoder
# ---------------------------------------------------------------------------


class TestAlarms:
    def test_empty_mask_means_no_alarms(self):
        s = decode_alarms(b"\x00" * 16)
        assert not s
        assert s.alarms == ()

    def test_single_known_alarm(self):
        mask = encode_alarms([Alarm.LIMIT_POS_J1])
        s = decode_alarms(mask)
        assert bool(s)
        assert Alarm.LIMIT_POS_J1 in s.alarms
        assert s.names() == ["LIMIT_POS_J1"]

    def test_multiple_alarms(self):
        mask = encode_alarms(
            [
                Alarm.OVERSPEED_J2,
                Alarm.LIMIT_POS_J3,
                Alarm.PUBLIC_RESET,
            ]
        )
        s = decode_alarms(mask)
        # Order is by code, not insertion.
        assert set(s.alarms) == {
            Alarm.OVERSPEED_J2,
            Alarm.LIMIT_POS_J3,
            Alarm.PUBLIC_RESET,
        }

    def test_unknown_alarm_kept_as_int(self):
        # Bit 0x7F isn't a named catalogue entry, but it sits in the known
        # 0x70 "OTHER" band, so it's labelled by band rather than as UNKNOWN.
        mask = encode_alarms([0x7F])
        s = decode_alarms(mask)
        assert s.alarms == (0x7F,)
        assert s.names() == ["OTHER_0x7F"]

    def test_describe_returns_per_alarm_strings(self):
        s = decode_alarms(encode_alarms([Alarm.LOST_STEP_J4]))
        descs = s.describe()
        assert len(descs) == 1
        assert "LOST_STEP_J4" in descs[0]
        assert "lost step" in descs[0]

    def test_short_buffer_is_padded(self):
        # Real firmware always sends 16 bytes; test that we don't crash on less.
        s = decode_alarms(b"\x01")
        assert Alarm.PUBLIC_RESET in s.alarms

    def test_round_trip_through_encode_decode(self):
        alarms = [Alarm.PLAN_INVERSE_RESOLVE, Alarm.OVERSPEED_J4, Alarm.LOST_STEP_J2]
        mask = encode_alarms(alarms)
        decoded = decode_alarms(mask)
        for a in alarms:
            assert a in decoded.alarms
