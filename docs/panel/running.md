# Running the panel

## Quick start

```bash
pydobotlab-panel
```

The console script is installed by `pip install -e .` (the same install that gives you the `pydobotlab` Python package).

On launch, the panel:

1. Probes localhost for a running broker. If none, spawns one in-process on `127.0.0.1:8765`.
2. Discovers Dobots on the machine (same logic as [`discover()`](../api/discovery.md#discover-only_known_adaptersfalse-timeout04-skip-listdiscovereddobot)).
3. Opens the **Hub window** with one row per arm.

Click **Connect** to open the Control Panel for any arm. Multiple arms produce multiple panel windows (one per arm); they all coexist.

## Command-line flags

| Flag | Default | What |
|------|---------|------|
| `--simulator` | (off) | Install the [simulator](../getting-started/simulator.md) before discovery, so the Hub shows fake arms. |
| `--arms N` | 2 | (Simulator only) Number of fake arms to spawn. |
| `--broker-host HOST` | `127.0.0.1` | Bind/connect address for the broker. |
| `--broker-port PORT` | `8765` | TCP port for the broker. |

So:

```bash
# real hardware, default settings
pydobotlab-panel

# no robots needed - try out the GUI fully
pydobotlab-panel --simulator --arms 3

# share an existing broker on a non-default port
pydobotlab-panel --broker-port 8800
```

## What the panel does to the arm on connect

Same as `Magician.connect()`:

1. Open the broker route (or direct serial if no broker reachable).
2. [`SET_QUEUED_CMD_CLEAR`](../protocol/command-ids.md) (245).
3. [`SET_QUEUED_CMD_START_EXEC`](../protocol/command-ids.md) (240).
4. Start a [pose stream](../api/pose-stream.md) at 50 Hz to drive the readout.

On window close, the panel does the inverse and (via the broker's reference counting) detaches the per-port serial transport when the *last* client lets go.

## Sharing the arm with a script

While the panel is open, just run your script - `Magician(port=...)` will detect the broker and route through it. No code change needed.

```bash
# Terminal 1
pydobotlab-panel

# Terminal 2 (panel still running)
python my_script.py
```

The panel's pose readout will update *while* your script is moving the arm.

## Two arms with two panels

```python
# examples/two_dobots_with_panels.py
from pydobotlab import Magician
from pydobotlab.panel import open_panel  # opens a ControlPanel window for an existing arm

bot_a = Magician(port="COM3")
bot_a.connect()
bot_b = Magician(port="COM4")
bot_b.connect()

# … script-side moves on either arm …

open_panel(bot_a)  # one panel per arm
open_panel(bot_b)
```

## Troubleshooting

* **Panel says "no Dobots found"** - same as `discover()` returning `[]`. Check `python -m serial.tools.list_ports`. If you see the arm but the panel doesn't, set `KNOWN_DOBOT_USB_IDS.add(...)` for your adapter (see [Discovery](../api/discovery.md#known_dobot_usb_ids)).
* **"port in use" when launching panel after a script crashed** - kill the orphaned Python process or reboot the arm. Defensive: pydobotlab opens the port `exclusive=True` on Linux so leaks are rare.
* **Panel closes but the broker keeps the arm open** - fixed in current pydobotlab via per-port reference counting (see [The DobotBroker](broker.md)).
