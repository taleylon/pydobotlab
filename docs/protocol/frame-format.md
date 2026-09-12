# Frame format

pydobotlab implements the **Dobot Communication Protocol V1.1.5**, the same protocol the official DobotStudio / DobotLink stack uses.

> **Reference document.** [Dobot Communication Protocol V1.1.5 (PDF)](https://www.alcom.no/wp-content/uploads/2019/11/Dobot-Communication-Protocol-V1.1.5-1.pdf). Every command ID and parameter layout in this guide is taken directly from that PDF - when in doubt, that's the canonical source.

The protocol is a **request / response** framing over a serial line at **115200 8N1**. Every command the host sends gets exactly one frame back, on the same line.

## Frame layout

```
+--------+--------+--------+--------+--------+--- ... ---+----------+
|  0xAA  |  0xAA  |  len   |   ID   |  Ctrl  |  Params   | Checksum |
+--------+--------+--------+--------+--------+--- ... ---+----------+
          header           |<------ "payload" of len bytes ----->|
```

| Field      | Bytes | Notes |
|------------|-------|-------|
| Header     | 2     | Always `0xAA 0xAA`. The reader resyncs on this. |
| Length     | 1     | Number of *payload* bytes that follow (i.e. `id + ctrl + params`). Excludes header and checksum. Max = 255. |
| ID         | 1     | The Dobot [command ID](command-ids.md). |
| Ctrl       | 1     | Bit 0 = `rw` (0 = get, 1 = set). Bit 1 = `isQueued` (0 = immediate, 1 = enqueue). See [Control byte](ctrl-byte.md). |
| Params     | 0..N  | Command-specific. All multi-byte fields are **little-endian**. |
| Checksum   | 1     | The byte that makes `(sum(payload) + checksum) mod 256 == 0`. I.e. `chk = (-sum(payload)) & 0xFF`. |

## Worked example - `GetPose`

Wire bytes the host sends:

```
AA AA   02   0A 00   F6
^^^^^   ^^   ^^^^^   ^^
header  len  id ctrl checksum
        2    10 0    -(10+0) & 0xFF = 0xF6
```

Wire bytes the arm replies (8 floats, 32 bytes):

```
AA AA  22  0A 00  <32 bytes of floats>  <chk>
```

The 32 payload bytes are 8 little-endian `float32`: `x, y, z, r, j1, j2, j3, j4`.

pydobotlab's `pack()` and `unpack()` (in [`pydobotlab/protocol.py`](https://github.com/anthropic/pydobotlab/blob/main/pydobotlab/protocol.py)) implement exactly this layout.

## Pack / unpack code

```python
HEADER = b"\xaa\xaa"


def calculate_checksum(payload: bytes) -> int:
    return (-sum(payload)) & 0xFF


def pack(cmd_id: int, ctrl: int, params: bytes = b"") -> bytes:
    payload_len = 2 + len(params)
    payload = bytes((cmd_id, ctrl)) + params
    return HEADER + bytes((payload_len,)) + payload + bytes((calculate_checksum(payload),))
```

(Unpack does the reverse, with header and checksum validation; the streaming reader resyncs on bad headers, which makes recovery from line glitches automatic.)

## Multi-byte field conventions

* All integers and floats are **little-endian**.
* Floats are 32-bit IEEE-754.
* Strings (e.g. device name) are 0-padded ASCII; the trailing zeros are stripped on unpack.

## `Frame` (decoded form)

Once a frame is unpacked pydobotlab gives you back a small dataclass:

```python
@dataclass(frozen=True, slots=True)
class Frame:
    cmd_id: int
    ctrl: int
    params: bytes

    @property
    def rw(self) -> bool:  # Ctrl bit 0
        return bool(self.ctrl & 0b01)

    @property
    def is_queued(self) -> bool:  # Ctrl bit 1
        return bool(self.ctrl & 0b10)
```

Lots of pydobotlab's `Magician` methods return `Frame` directly (or a value parsed out of `frame.params`).

## Special case - queued response

When you send a write with `isQueued=1`, the response payload is *always* a single `uint64` - the **queued-command index** assigned by the firmware. That's the integer `move_to`/`set_home`/`set_endeffector_*` return.
