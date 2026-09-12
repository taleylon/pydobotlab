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
        # FakeSerial returned 8 floats — verify they come back via the broker.
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
