"""Regression coverage for fragmented TCP reads and failed connection cleanup."""

from __future__ import annotations

import struct

import pytest
import serial

from pydobotlab import Dobot, DobotConnectionError, DobotProtocolError
from pydobotlab.commands import CommandID
from pydobotlab.protocol import pack, pack_floats, unpack_floats
from pydobotlab.transport import BrokerTransport, SerialTransport, is_port_claimed


class FragmentedSocket:
    """Deliver each TCP byte separately, including the length prefix."""

    def __init__(self, incoming: bytes, *, fail_connect: bool = False):
        self.incoming = bytearray(incoming)
        self.fail_connect = fail_connect
        self.closed = False
        self.sent = bytearray()

    def connect(self, address):
        if self.fail_connect:
            raise OSError("connection refused")

    def settimeout(self, timeout):
        pass

    def sendall(self, data):
        self.sent.extend(data)

    def recv(self, byte_count):
        received = bytes(self.incoming[: min(1, byte_count)])
        del self.incoming[: len(received)]
        return received

    def shutdown(self, how):
        pass

    def close(self):
        self.closed = True


def test_broker_reads_fragmented_header_and_payload(monkeypatch):
    response = pack(CommandID.GET_POSE, 0, pack_floats(1, 2, 3, 4, 5, 6, 7, 8))
    connection = FragmentedSocket(b"\x00" + struct.pack("!H", len(response)) + response)
    monkeypatch.setattr("pydobotlab.transport.socket.socket", lambda *args: connection)
    transport = BrokerTransport("/dev/test-fragmented")
    transport.open()
    try:
        frame = transport.send_frame(CommandID.GET_POSE, 0)
        assert unpack_floats(frame.params) == (1, 2, 3, 4, 5, 6, 7, 8)
    finally:
        transport.close()
    assert connection.closed


@pytest.mark.parametrize("reply", [b"", b"\x01", b"\x02", b"\x03"])
def test_failed_broker_handshake_closes_socket(monkeypatch, reply):
    connection = FragmentedSocket(reply)
    monkeypatch.setattr("pydobotlab.transport.socket.socket", lambda *args: connection)
    transport = BrokerTransport("/dev/test-handshake")
    with pytest.raises(DobotConnectionError):
        transport.open()
    assert connection.closed
    assert not transport.is_open


def test_refused_broker_connection_closes_socket(monkeypatch):
    connection = FragmentedSocket(b"", fail_connect=True)
    monkeypatch.setattr("pydobotlab.transport.socket.socket", lambda *args: connection)
    transport = BrokerTransport("/dev/test-refused")
    with pytest.raises(DobotConnectionError):
        transport.open()
    assert connection.closed


@pytest.mark.parametrize("frame_length", [0, 5, 260, 65535])
def test_invalid_broker_frame_length_is_rejected(monkeypatch, frame_length):
    connection = FragmentedSocket(b"\x00" + struct.pack("!H", frame_length))
    monkeypatch.setattr("pydobotlab.transport.socket.socket", lambda *args: connection)
    transport = BrokerTransport("/dev/test-length")
    transport.open()
    try:
        with pytest.raises(DobotProtocolError, match="frame length"):
            transport.send_frame(CommandID.GET_POSE, 0)
    finally:
        transport.close()


def test_serial_setup_failure_closes_device_and_releases_port(monkeypatch):
    class FailingSerial:
        is_open = False

        def open(self):
            self.is_open = True

        def reset_input_buffer(self):
            raise serial.SerialException("buffer reset failed")

        def close(self):
            self.is_open = False

    serial_port = FailingSerial()
    monkeypatch.setattr("pydobotlab.transport.serial.Serial", lambda: serial_port)
    transport = SerialTransport("/dev/test-reset-failure")
    with pytest.raises(DobotConnectionError, match="buffer reset failed"):
        transport.open()
    assert not serial_port.is_open
    assert not transport.is_open
    assert not is_port_claimed(transport.port)


def test_device_queue_initialization_failure_closes_transport(monkeypatch):
    class FailingTransport:
        is_open = False

        def open(self):
            self.is_open = True

        def send_frame(self, *args):
            raise DobotConnectionError("queue initialization failed")

        def close(self):
            self.is_open = False

    transport = FailingTransport()
    monkeypatch.setattr("pydobotlab.device.SerialTransport", lambda *args: transport)
    robot = Dobot("/dev/test-queue-failure", via_broker=False)
    with pytest.raises(DobotConnectionError, match="queue initialization failed"):
        robot.connect()
    assert not transport.is_open
    assert not robot.is_open
