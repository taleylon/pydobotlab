# The DobotBroker

The broker is a local TCP server that owns serial ports and relays Dobot frames between them and any number of clients, such as the control panel and scripts. It listens on `127.0.0.1:8765` by default. The panel starts one when none is running.

```
 ┌──────────────┐  TCP   ┌──────────────────┐  serial  ┌──────┐
 │ ControlPanel │───────►│                  │─────────►│      │
 │ (Magician)   │        │   DobotBroker    │          │  arm │
 └──────────────┘        │                  │          │      │
 ┌──────────────┐  TCP   │                  │          └──────┘
 │ script       │───────►│                  │
 │ (Magician)   │        └──────────────────┘
 └──────────────┘
```

`Magician` connects through the broker when one is running. When none is running, it raises `DobotConnectionError` if the control panel is installed, and opens the serial port directly otherwise or with `require_panel=False`. See [`Magician`](../api/magician.md#magician), [Running scripts](running.md#scripts), and the [Broker API](../api/broker.md).

## Wire protocol

This is the protocol between `Magician` and the broker. Dobot frames are relayed unchanged inside it.

### List ports

Client to broker: `0x00`.

Broker to client: `u8 N`, then `N` entries of `u8 LEN | port[LEN]` (ASCII), one for each attached port.

### Attach

Client to broker: `0x01 | u8 LEN | port[LEN]` (ASCII).

Broker to client, one byte:

| Reply | Meaning |
|---|---|
| `0x00` | Attached. The connection switches to frame relay. |
| `0x01` | The port could not be opened. |
| `0x02` | The port is busy. |
| `0x03` | Unknown command. |
| `0x04` | Permission denied. |

### Frame relay

Both directions: `u16 LEN (big-endian) | DOBOT_FRAME[LEN]`. Each client request produces one reply. The frames are the [wire frames](../protocol/frame-format.md) that `Magician` would otherwise send to the serial port.

### Errors

If the arm does not answer, the serial link fails, or a request is malformed, the broker replies with `u16 0 | u8 CODE | u8 LEN | message[LEN]` instead of a frame.

| Code | Meaning | Raised by the client as |
|---|---|---|
| `1` | Timeout | `DobotTimeoutError` |
| `2` | Connection failure | `DobotConnectionError` |
| `3` | Protocol error | `DobotProtocolError` |
| `4` | Internal error | `DobotConnectionError` |

The connection stays open after an error, except after a malformed byte stream, when the broker closes it.

### Timeouts

A client may be idle between requests for any length of time. A frame that starts to arrive and then stalls is dropped. TCP keepalive removes clients that disappear without closing the connection. A client that times out waiting for a reply closes the connection.

## Port ownership

A port requested by a client and not yet attached is opened on demand. The broker closes it when its last client disconnects. A port opened with [`DobotBroker.attach`](../api/broker.md#dobotbroker-attach) stays open until it is detached or the broker stops.

Requests for one port are handled one at a time, so clients never receive partial frames.

## Disabling the broker

Use `Magician(via_broker=False)` to always open the serial port directly, also while a broker is running, for example when TCP connections are not available or when the extra hop matters.
