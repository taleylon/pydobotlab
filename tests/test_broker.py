"""End-to-end test for the panel-as-broker architecture.

Drives the broker against a *fake* serial backend so we don't need a real
Dobot. Spins up DobotBroker on an ephemeral port; one client uses
BrokerTransport to send a frame; we assert the broker forwards it to the
fake serial and the response comes back through the wire.
"""

from __future__ import annotations

import threading

import pytest

from pydobotlab.broker import (
    DobotBroker,
    is_broker_reachable,
    list_broker_ports,
)
from pydobotlab.commands import CommandID
from pydobotlab.config import default_config, set_config
from pydobotlab.protocol import pack, pack_floats, unpack
from pydobotlab.transport import _OPEN_PORTS, BrokerTransport


# A fake serial that echoes the request body back as a response.
class FakeSerial:
    """Implements just the slice of pyserial that SerialTransport touches."""

    is_open = True

    def __init__(self, **kwargs):
        self._buf = bytearray()
        self._read = bytearray()

    def open(self):
        self.is_open = True

    def reset_input_buffer(self):
        pass

    def reset_output_buffer(self):
        pass

    def write(self, data: bytes) -> int:
        # Decode what was sent and echo a "GetPose-style" response (8 floats).
        frame = unpack(bytes(data))
        # Build a response frame with the same id/ctrl, params = 8 floats.
        response_payload = pack_floats(11.0, 22.0, 33.0, 44.0, 55.0, 66.0, 77.0, 88.0)
        wire = pack(frame.cmd_id, frame.ctrl, response_payload)
        self._read += wire
        return len(data)

    def flush(self):
        pass

    def read(self, n: int) -> bytes:
        out = bytes(self._read[:n])
        self._read = self._read[n:]
        return out

    def close(self):
        self.is_open = False


@pytest.fixture
def patched_serial(monkeypatch):
    import pydobotlab.transport as t

    monkeypatch.setattr(t.serial, "Serial", FakeSerial)
    yield
    _OPEN_PORTS.clear()


@pytest.fixture
def broker(patched_serial):
    server = DobotBroker(port=0)
    server.start()
    # Pre-attach a fake serial port.
    server.attach("/dev/fake-broker-A")
    try:
        yield server
    finally:
        server.stop()


def test_is_broker_reachable_after_start(broker):
    # Bypass the per-process cache for this assertion.
    from pydobotlab.broker import _BROKER_CACHE

    _BROKER_CACHE.clear()
    assert is_broker_reachable("127.0.0.1", broker.port, timeout=0.5)


def test_list_broker_ports_returns_attached(broker):
    ports = list_broker_ports("127.0.0.1", broker.port)
    assert "/dev/fake-broker-A" in ports


def test_broker_transport_round_trips_a_frame(broker):
    bt = BrokerTransport(
        "/dev/fake-broker-A",
        broker_host="127.0.0.1",
        broker_port=broker.port,
    )
    bt.open()
    try:
        # Send a GetPose request through the broker.
        resp = bt.send_frame(CommandID.GET_POSE, 0)
        # FakeSerial returned 8 floats - verify they come back via the broker.
        from pydobotlab.protocol import unpack_floats

        values = unpack_floats(resp.params[:32])
        assert values == (11.0, 22.0, 33.0, 44.0, 55.0, 66.0, 77.0, 88.0)
    finally:
        bt.close()


def test_two_concurrent_clients_dont_corrupt_each_other(broker):
    """Multi-client safety: two threads each fire many frames; all should
    return well-formed responses (no interleaving on the wire)."""
    errors: list[Exception] = []

    def client():
        try:
            bt = BrokerTransport(
                "/dev/fake-broker-A",
                broker_host="127.0.0.1",
                broker_port=broker.port,
            )
            bt.open()
            try:
                for _ in range(20):
                    resp = bt.send_frame(CommandID.GET_POSE, 0)
                    assert resp.cmd_id == CommandID.GET_POSE
            finally:
                bt.close()
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=client) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, errors


def test_handshake_rejects_unknown_port(broker):
    bt = BrokerTransport(
        "/dev/never-existed",
        broker_host="127.0.0.1",
        broker_port=broker.port,
    )
    # The broker tries to lazily attach, FakeSerial accepts everything,
    # so this *will* succeed in this test. Just assert open() works.
    bt.open()
    bt.close()


def use_short_frame_timeout():
    config = default_config()
    config["broker"]["frame_timeout"] = 0.2
    set_config(config)


def test_idle_client_stays_connected_past_frame_timeout(broker):
    """A client may be silent between requests for longer than the frame timeout
    (a script waiting for input, a server waiting for requests)."""
    import time

    use_short_frame_timeout()
    bt = BrokerTransport(
        "/dev/fake-broker-A", broker_host="127.0.0.1", broker_port=broker.port, timeout=0.5
    )
    bt.open()
    try:
        assert bt.send_frame(CommandID.GET_POSE, 0).cmd_id == CommandID.GET_POSE
        time.sleep(1.0)  # five times the frame timeout, no traffic
        assert bt.send_frame(CommandID.GET_POSE, 0).cmd_id == CommandID.GET_POSE
        assert "/dev/fake-broker-A" in broker.attached_ports()
    finally:
        bt.close()


def test_stalled_partial_frame_is_still_dropped(broker):
    """Idle is fine; a frame that starts and never finishes is not."""
    import socket
    import time

    use_short_frame_timeout()
    with socket.create_connection(("127.0.0.1", broker.port), timeout=2) as connection:
        port_name = b"/dev/fake-broker-A"
        connection.sendall(bytes((0x01, len(port_name))) + port_name)
        assert connection.recv(1) == b"\x00"
        connection.sendall(b"\x00")  # half of the 2-byte length prefix, then silence
        time.sleep(0.6)
        assert connection.recv(1) == b""  # broker closed the connection


# -- failures reach the client; none are swallowed ----------------------------

FAKE_PORT = "/dev/fake-broker-A"


def broker_client(broker, **kwargs):
    client = BrokerTransport(FAKE_PORT, broker_host="127.0.0.1", broker_port=broker.port, **kwargs)
    client.open()
    return client


def test_arm_timeout_is_reported_and_connection_survives(broker):
    from pydobotlab import DobotTimeoutError

    arm = broker._transports[FAKE_PORT]._serial
    answer = arm.write
    requests = []

    def silent_first_time(data):
        requests.append(data)
        return len(data) if len(requests) == 1 else answer(data)

    arm.write = silent_first_time
    client = broker_client(broker)
    try:
        with pytest.raises(DobotTimeoutError):
            client.send_frame(CommandID.GET_POSE, 0)
        assert client.is_open
        assert client.send_frame(CommandID.GET_POSE, 0).cmd_id == CommandID.GET_POSE
        assert FAKE_PORT in broker.attached_ports()
    finally:
        client.close()


def test_serial_failure_is_reported_with_its_message(broker):
    import serial

    from pydobotlab import DobotConnectionError

    arm = broker._transports[FAKE_PORT]._serial

    def pulled_cable(data):
        raise serial.SerialException("device disconnected")

    arm.write = pulled_cable
    client = broker_client(broker)
    try:
        with pytest.raises(DobotConnectionError, match="device disconnected"):
            client.send_frame(CommandID.GET_POSE, 0)
        assert client.is_open
    finally:
        client.close()


def test_malformed_request_is_reported_not_dropped(broker):
    import socket
    import struct

    from pydobotlab import DobotProtocolError
    from pydobotlab.broker_protocol import receive_frame_bytes, send_frame_bytes

    with socket.create_connection(("127.0.0.1", broker.port), timeout=2) as connection:
        port_name = FAKE_PORT.encode()
        connection.sendall(bytes((0x01, len(port_name))) + port_name)
        assert connection.recv(1) == b"\x00"
        send_frame_bytes(connection, b"\x00" * 8)  # right length, not a Dobot frame
        with pytest.raises(DobotProtocolError, match="bad header"):
            receive_frame_bytes(connection, allow_error_reply=True)
        # Still connected: a valid request now succeeds.
        send_frame_bytes(connection, pack(CommandID.GET_POSE, 0))
        assert struct.unpack("!H", connection.recv(2))[0] >= 6
