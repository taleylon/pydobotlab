# Control panel

`pydobotlab-panel` is a desktop control panel for the Magician, built with PySide6. It shows the arm pose live while a script is running, and a script and the panel can control the same arm at the same time through the [broker](broker.md).

PySide6 is installed with the `gui` extra:

```bash
python -m pip install "pydobotlab[gui]"
```

## Windows

**Hub.** Lists the arms found, by port (`COM3`, `/dev/ttyACM0`). Only ports identified as a Dobot Magician ([Discovery](../api/discovery.md)) are listed as arms; ports that answer otherwise are under *Other devices (n)*, collapsed until clicked. *Refresh* scans again. *Open Control Panel* opens a control panel for the selected arm.

The hub and each control panel show the pydobotlab version at the bottom right.

**Control panel.** One window per arm:

- Pose readout: X, Y, Z, R and J1 to J4, refreshed at 30 Hz.
- Jog pads for Cartesian and joint motion. Hold a segment to jog and release to stop.
- Speed slider: the arm's point-to-point and jog speed ([`motion_params`](../api/speed.md#motion_params), [`set_jog_common_params`](../api/speed.md#set_jog_common_params)). The speed is stored in the arm, so scripts running on the same arm use it, and the slider follows changes made by scripts. Opening a panel keeps the arm's current speed.
- JUMP parameters: lift height and Z limit.
- Home and Clear Alarm buttons. If an alarm comes back after clearing, Clear Alarm shows the alarm and its remedy, and the alarm stays active.
- End-effector controls for the suction cup and gripper. They act at once, also while a script moves the arm.
- Connection indicator: checks the arm every 2 seconds and shows *Disconnected*, with a *Reconnect* button, after 3 consecutive failed checks.
- Alarm banner: one line per active alarm, in the form `TAG: remedy`.

## Structure

```
                        ┌─────────────────┐
                        │   Hub window    │
                        └────────┬────────┘
                                 │ creates one window per arm
        ┌────────────────────────┼────────────────────────┐
        ▼                        ▼                        ▼
 ControlPanel(/dev/A)    ControlPanel(/dev/B)    ControlPanel(/dev/C)
        │                        │                        │
        └─── PoseStreamer ───────┼─── PoseStreamer ───────┘
                                 │
                                 ▼
                          DobotBroker (TCP 127.0.0.1:8765)
                                 │
                       per-port SerialTransport
                                 │
                              the arms
```

Each `ControlPanel` has its own `Magician` and its own `PoseStreamer`, a `QThread` that polls `get_pose` and emits Qt signals. All panels connect through the broker, so scripts can share each arm.

See [Running the panel](running.md) and [The DobotBroker](broker.md).
