# Running without hardware (simulator)

`pydobotlab` ships with a built-in simulator so you can develop, demo, and run unit tests without an arm plugged in. The simulator monkey-patches `pyserial` at the bottom of the stack, so the rest of the library — `Magician`, the broker, the panel, your scripts — runs unchanged.

## From a script

```python
from pydobotlab.simulator import install_simulator

install_simulator(arms=2)  # creates /dev/sim0 and /dev/sim1

from pydobotlab import Magician

with Magician(port="/dev/sim0") as bot:
    bot.set_home()
    bot.move_to(200, 0, 50, 0)
    print(bot.get_pose())
```

`install_simulator(arms=N)` is idempotent — calling it twice in the same process is a no-op. It:

1. Replaces `serial.Serial` with a fake that talks to an in-memory `FakeDobot`.
2. Replaces `serial.tools.list_ports.comports()` so discovery sees fake ports as if they were real Dobot adapters.
3. Pre-creates the named arms (`/dev/sim0`, `/dev/sim1`, ...) so they're available before the first `connect()`.

Each fake arm has a tiny motion model that interpolates toward the latest target so pose readouts animate visibly. JOG, multi-stage HOME, the speed slider, JUMP-mode, and the workspace check are all simulated.

## From the panel

Pass `--simulator` to spin up the GUI against fake arms:

```bash
pydobotlab-panel --simulator --arms 2
```

This is the recommended way to demo the full system without hardware.

## What the simulator models

| Feature                                       | Simulated? |
|-----------------------------------------------|-----------|
| Pose interpolation toward PTP targets         | yes |
| JOG (live nudge in coord/joint mode)          | yes |
| Multi-stage HOME (lift → swing → descend)     | yes |
| Speed slider (PTP & JOG vel/acc ratios)       | yes |
| JUMP-mode params (height, zlimit)             | yes |
| Workspace bounds + alarm raise on violation   | yes |
| Alarm bitmask read/clear                      | yes |
| Multi-client via the broker                   | yes |
| End-effector valves & I/O                     | acked but not visualised |

Anything not explicitly modelled (most reads) returns plausible zeros so your code doesn't crash. The simulator's source is `pydobotlab/simulator.py`.

## Stopping the fakes

In tests:

```python
from pydobotlab.simulator import stop_all

stop_all()  # joins all FakeDobot background threads
```

You normally don't need to call this — the threads are daemons and exit with the process.

## Next

* [API Reference overview →](../api/overview.md)
