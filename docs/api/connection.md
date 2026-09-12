# Connection lifecycle

Methods that open and close the serial / broker channel to the arm. The `Magician` constructor doesn't talk to hardware; that happens in `connect()`.

## `Magician(port=None, baudrate=115200, timeout=1.0, *, auto_start_queue=True, only_known_adapters=False, via_broker="auto", broker_host="127.0.0.1", broker_port=8765)`

**Purpose.** Construct a Magician driver. No I/O happens here.

See [Connecting to an arm](../getting-started/connect.md) for the full table of constructor options.

---

## `connect() -> None`

**Purpose.** Resolve the port, open the line, and prepare the firmware queue.

**Inputs.** None.

**Returns.** `None`.

**Raises.**
* [`DobotConnectionError`](errors.md#dobotconnectionerror) - port not found or open failed.
* [`DobotPortInUseError`](errors.md#dobotportinuseerror-extends-dobotconnectionerror) - a second Magician in this process already owns this port, or the OS refused exclusive access.

**Protocol.** No single command - at the wire level this is the OS-side `serial.Serial.open()` (or a TCP `ATTACH` to the broker), followed by:
* [`SET_QUEUED_CMD_CLEAR`](../protocol/command-ids.md) (245)
* [`SET_QUEUED_CMD_START_EXEC`](../protocol/command-ids.md) (240)

The two queue commands are skipped if you constructed with `auto_start_queue=False`.

**Example.**

```python
bot = Magician(port="/dev/ttyUSB0")
bot.connect()
# … work …
bot.disconnect()
```

---

## `disconnect() -> None`

**Purpose.** Stop any running pose stream, stop the firmware queue, and close the transport.

**Inputs.** None.

**Returns.** `None`.

**Raises.** Doesn't raise - the close path swallows transport errors so you can call it from `finally:` blocks safely.

**Protocol.** Sends [`SET_QUEUED_CMD_STOP_EXEC`](../protocol/command-ids.md) (241) on the way out, then closes the OS handle (or sends a TCP close to the broker).

---

## `__enter__() / __exit__()` - context-manager support

**Purpose.** Use `Magician` with `with`, which calls `connect()` on entry and `disconnect()` on exit even if an exception is raised inside the block.

**Example.**

```python
with Magician() as bot:
    bot.move_to(200, 0, 50, 0)
# Disconnected here - even if the move raised.
```

---

## `port` *(read-only property)*

**Purpose.** The OS-resolved port name once `connect()` has run. `None` before connection.

**Returns.** `str | None`.

---

## `is_open` *(read-only property)*

**Purpose.** `True` while the underlying transport is open.

**Returns.** `bool`.

---

## Process-level helpers

These live in `pydobotlab.discovery` and are documented on the [Discovery](discovery.md) page, but you'll see them often when wrangling multi-arm setups:

* `is_port_in_use(port)` - `True` if some `Magician` in *this process* currently owns the port.
* `find_free_port(only_known_adapters=False)` - return the first port that answers like a Dobot and isn't already claimed.
