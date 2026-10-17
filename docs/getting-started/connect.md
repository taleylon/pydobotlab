# Connecting to an arm

Start the [control panel](../panel/running.md) before the script, and keep it running until the script ends:

```bash
pydobotlab-panel
```

`Magician` connects through the panel, so the panel and the script control the same arm. When the panel is not running, `connect` raises [`DobotConnectionError`](../api/errors.md#dobotconnectionerror). See [Running scripts](../panel/running.md#scripts).

## Automatic port selection

Without a `port` argument, `Magician` probes the serial ports and uses the first one that answers as a Dobot. See [Discovery](../api/discovery.md).

```python
from pydobotlab import Magician

with Magician() as bot:
    print(bot.get_pose())
```

## Specifying a port

Pass the port name to select an arm explicitly, for example when several arms are connected.

```python
bot = Magician(port="/dev/ttyUSB0")  # macOS and Linux
bot = Magician(port="COM3")  # Windows
bot.connect()
# ...
bot.disconnect()
```

`with` calls `connect` on entry and `disconnect` on exit:

```python
with Magician(port="COM3") as bot:
    bot.set_home()
```

The remaining constructor options (broker routing, timeouts, logging) are listed under [`Magician`](../api/magician.md#magician). Default settings come from a [configuration file](../api/config.md).

## Multiple arms

Each `Magician` instance owns one port, so several arms can be driven from one script:

```python
import threading

from pydobotlab import Magician


def run(port, label):
    with Magician(port=port) as bot:
        bot.set_home()
        bot.ptp(mode=1, x=200, y=0, z=0, r=0)  # MOVJ_XYZ
        print(label, bot.get_pose())


left = threading.Thread(target=run, args=("/dev/ttyUSB0", "left"))
right = threading.Thread(target=run, args=("/dev/ttyUSB1", "right"))
left.start()
right.start()
left.join()
right.join()
```

`mode=1` selects a joint-interpolated move to a Cartesian target. See [`PTPMode`](../api/motion.md#ptpmode). Complete examples are in `examples/multi_dobot.py` and `examples/two_dobots_with_panels.py`.

## Without the control panel

With `require_panel=False`, `Magician` connects through the panel when it is running and opens the serial port directly otherwise:

```python
with Magician(require_panel=False) as bot:
    print(bot.get_pose())
```

While such a script holds the port, the panel cannot open the arm.

## Next

- [Hello, Magician](first-script.md)
- [Running without hardware](simulator.md)
