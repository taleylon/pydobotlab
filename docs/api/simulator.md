# Simulator

Module `pydobotlab.simulator`. Simulated arms that replace the serial layer, for use without hardware. A walkthrough is in [Running without hardware](../getting-started/simulator.md).

| Member | Description |
|---|---|
| [`install_simulator`](#install_simulator) | Replace the serial layer with simulated arms. |
| [`is_simulator_installed`](#is_simulator_installed) | Whether the simulator is installed. |
| [`stop_all`](#stop_all) | Stop and remove all simulated arms. |

---

## `install_simulator` {#install_simulator}

```python
pydobotlab.simulator.install_simulator(arms=None) -> list[str]
```

Replace the serial layer with simulated arms.

After the call, `Magician`, port discovery, the broker, and the control panel use the simulated arms. Port discovery lists only the simulated ports. Calling the function again does not reinstall the simulator.

**Parameters**

| Name | Type | Description |
|---|---|---|
| `arms` | `int` or `None`, default `None` | Number of simulated arms, at least 1. `None` uses the configured default, `2` unless changed. |

**Returns** `list[str]`: port names, `/dev/sim0`, `/dev/sim1`, and so on.

**Notes**

Point-to-point targets outside the [workspace](../guide/workspace.md) of the real arm set the `PLAN_INVERSE_CALCULATION` alarm, as on the real arm.

**Example**

```python
from pydobotlab.simulator import install_simulator

port = install_simulator(arms=1)[0]
with Magician(port=port, via_broker=False) as bot:
    bot.ptp(mode=1, x=200, y=0, z=50, r=0)  # MOVJ_XYZ
```

---

## `is_simulator_installed` {#is_simulator_installed}

```python
pydobotlab.simulator.is_simulator_installed() -> bool
```

Return whether [`install_simulator`](#install_simulator) has been called in this process.

---

## `stop_all` {#stop_all}

```python
pydobotlab.simulator.stop_all() -> None
```

Stop the background threads of all simulated arms and remove the arms.
