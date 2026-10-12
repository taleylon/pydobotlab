# Frame format

pydobotlab implements the [Dobot Communication Protocol V1.1.5](../Dobot-Communication-Protocol-V1.1.5.pdf). The command IDs and parameter layouts in this reference are taken from that document.

The protocol is request and response over a serial line at 115200 baud, 8N1. The arm answers every command with exactly one frame.

## Layout

```
+--------+--------+--------+--------+--------+--- ... ---+----------+
|  0xAA  |  0xAA  |  len   |   ID   |  Ctrl  |  Params   | Checksum |
+--------+--------+--------+--------+--------+--- ... ---+----------+
          header           |<------ payload of len bytes ------>|
```

| Field | Bytes | Description |
|---|---|---|
| Header | 2 | `0xAA 0xAA`. The reader resynchronizes on it. |
| Length | 1 | Number of payload bytes: ID, control byte, and parameters. At most 255. |
| ID | 1 | [Command ID](command-ids.md). |
| Ctrl | 1 | Bit 0 is `rw` (0 = get, 1 = set). Bit 1 is `isQueued` (0 = immediate, 1 = queued). See [Control byte](ctrl-byte.md). |
| Params | 0 to 253 | Command-specific. |
| Checksum | 1 | `(-sum(payload)) & 0xFF`, so that the payload sum plus the checksum is 0 modulo 256. |

## Field encoding

- Integers and floats are little-endian.
- Floats are 32-bit IEEE 754.
- Strings, such as the device name, are zero-padded ASCII. Trailing zeros are removed when reading.

## Example: `GetPose`

Request:

```
AA AA   02   0A 00   F6
header  len  id ctrl  checksum
```

The length is 2 (ID and control byte). The checksum is `-(0x0A + 0x00) & 0xFF = 0xF6`.

Response with eight 32-bit floats (32 bytes):

```
AA AA  22  0A 00  <32 bytes>  <checksum>
```

The floats are `x, y, z, r, j1, j2, j3, j4`.

## Queued responses

The response to a set command with `isQueued=1` is a single `uint64`: the queue index assigned by the firmware. This is the value returned by `ptp`, `set_endeffector_*`, and the other queued methods.

## Implementation

`pydobotlab.protocol` provides `pack` and `unpack` for frames, `read_frame` for streaming reads, and the [`Frame`](../api/low-level.md#frame) class for decoded frames. `unpack` raises `DobotProtocolError` for a bad header, length, or checksum. `read_frame` skips bytes until it finds a header.
