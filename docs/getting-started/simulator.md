# Running without hardware

The simulator replaces the serial layer with in-memory arms, so `Magician`, the broker, the control panel, and scripts run unchanged without an arm. See [Simulator](../api/simulator.md) for the API.

## In a script

```python
from pydobotlab.simulator import install_simulator

install_simulator(arms=2)  # creates /dev/sim0 and /dev/sim1

from pydobotlab import Magician

with Magician(port="/dev/sim0", via_broker=False) as bot:
    bot.set_home()
    bot.ptp(mode=1, x=200, y=0, z=50, r=0)  # MOVJ_XYZ
    print(bot.get_pose())
```

`via_broker=False` connects to the simulated arm in the script's process instead of through the control panel. `mode=1` selects a joint-interpolated move to a Cartesian target. See [`PTPMode`](../api/motion.md#ptpmode).

`install_simulator` replaces `serial.Serial` with a simulated port, makes port discovery list the simulated arms, and creates the arms. Calling it again in the same process has no effect.

## In the control panel

```bash
pydobotlab-panel --simulator --simulator-arms 2
```

Scripts then connect to the simulated arms through the panel, without `install_simulator`, for example with `Magician(port="/dev/sim0")`.

## Simulated behavior

| Feature | Simulated |
|---|---|
| Pose interpolation toward point-to-point targets | Yes |
| Jogging in Cartesian and joint modes | Yes |
| Multi-stage homing | Yes |
| Velocity and acceleration ratios | Yes |
| JUMP parameters | Yes |
| Workspace limits and the out-of-workspace alarm | Yes |
| Alarm read and clear | Yes |
| Multiple clients through the broker | Yes |
| End-effector and I/O commands | Acknowledged, not visualized |

Commands that are not simulated return zero values.
## Stopping the simulated arms

Tests can stop all simulated arms with `stop_all()`. The background threads are daemon threads and also end with the process.

```python
from pydobotlab.simulator import stop_all

stop_all()
```

## Next

- [API reference](../api/overview.md)
