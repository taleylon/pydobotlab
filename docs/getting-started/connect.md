# Connecting to an arm

## The simplest case — auto-pick

If you have one arm plugged in, this is enough:

```python
from pydobotlab import Magician

with Magician() as bot:
    print(bot.get_pose())
```

`Magician()` with no `port` argument scans the OS's serial devices, sends a probe frame to each candidate, and uses the first one that answers like a Dobot. The port discovery logic is documented in detail under [Discovery](../api/discovery.md).

## Specifying a port

If you have several arms, or want to be explicit, pass the port name:

```python
bot = Magician(port="/dev/ttyUSB0")  # macOS / Linux
bot = Magician(port="COM3")  # Windows
bot.connect()
# … use it …
bot.disconnect()
```

Or as a context manager (auto-disconnect on exit):

```python
with Magician(port="COM3") as bot:
    bot.set_home()
```

## Connection options

`Magician(...)` accepts:

| Argument              | Default       | What it does |
|-----------------------|---------------|--------------|
| `port`                | `None`        | OS serial device path. `None` = auto-pick. |
| `baudrate`            | `115200`      | Only baud rate the firmware speaks; rarely overridden. |
| `timeout`             | `1.0`         | Per-byte read timeout (seconds). |
| `auto_start_queue`    | `True`        | After opening, clear & start the firmware queue. Set `False` if you want manual control. |
| `only_known_adapters` | `False`       | When auto-picking, restrict to USB adapters known to be Dobot (CH340, Silicon Labs CP21xx). |
| `via_broker`          | `"auto"`      | `"auto"` = use a running broker if one is reachable, else direct serial. `True` = require broker. `False` = always direct. |
| `broker_host`         | `"127.0.0.1"` | Broker host (only relevant if `via_broker` allows broker). |
| `broker_port`         | `8765`        | Broker TCP port. |

## Multiple arms in one script

`Magician` instances are completely independent — each owns its own serial port (or its own broker channel). You can drive several arms in parallel from the same script:

```python
from pydobotlab import Magician
import threading


def run(port, label):
    with Magician(port=port) as bot:
        bot.set_home()
        bot.move_to(200, 0, 0, 0)
        print(label, bot.get_pose())


t1 = threading.Thread(target=run, args=("/dev/ttyUSB0", "left"))
t2 = threading.Thread(target=run, args=("/dev/ttyUSB1", "right"))
t1.start()
t2.start()
t1.join()
t2.join()
```

See `examples/multi_dobot.py` and `examples/two_dobots_with_panels.py` for fuller examples.

## Sharing one arm with the control panel

If `pydobotlab-panel` is already running, start your script normally — `Magician()` will detect the broker on `127.0.0.1:8765` and route through it automatically. Both the panel's live readout and your script's commands will be interleaved on the same arm.

```python
# Panel running in another terminal? Same code as before — no change needed.
with Magician(port="COM3") as bot:
    bot.move_to(200, 0, 0, 0)
```

For the gritty details of how broker routing works, see [The DobotBroker](../panel/broker.md).

## Next

* [Hello, Magician — your first script →](first-script.md)
* [Running without hardware (simulator) →](simulator.md)
