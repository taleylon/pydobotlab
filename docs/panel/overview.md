# Control panel

`pydobotlab-panel` is a desktop control panel for the Magician, built with PySide6. It shows the arm pose live while a script is running, and a script and the panel can control the same arm at the same time through the [broker](broker.md).

PySide6 is installed with the `gui` extra:

```bash
python -m pip install "pydobotlab[gui]"
```

## Windows

**Hub.** Lists the arms found as *Dobot Magician 1*, *Dobot Magician 2*, and so on, numbered in the order they are found; an arm keeps its number while the panel runs. With `--dev`, each arm's port (`COM3`, `/dev/ttyACM0`) is shown after its name, in the hub and in its control panel. Only ports identified as a Dobot Magician ([Discovery](../api/discovery.md)) are listed as arms; ports that answer otherwise are under *Other devices (n)*, below a line, collapsed until clicked. When no arm is found, the hub says so and why, if known; the ports tried are listed only with `--dev`. A permission problem is explained in a box above the list. *Refresh* scans again. *Open Control Panel* opens a control panel for the selected arm.

The hub and each control panel show the pydobotlab version at the bottom right.

**Control panel.** One window per arm:

- Pose readout: X, Y, Z, R and J1 to J4, refreshed at 30 Hz. Click a value, type a target, and press Enter to move the arm there; the other three values of the same row stay as they are. Esc cancels. The move is a [`ptp`](../api/motion.md#ptp): [`MOVJ_XYZ`](../api/motion.md#ptpmode) for X, Y, Z and R, `MOVJ_ANGLE` for J1 to J4. As in a script, a target out of reach is refused with an alarm, shown in the banner; the arm does not move. Values cannot be typed while a typed move runs or while the arm homes.
- Jog pads for Cartesian and joint motion. Hold a segment to jog and release to stop. The pads work during an alarm; the arm refuses a jog it cannot make. A joint-limit alarm ends by itself when the joint is jogged back off the limit.
- Speed slider: the arm's point-to-point and jog speed ([`motion_params`](../api/speed.md#motion_params), [`set_jog_common_params`](../api/speed.md#set_jog_common_params)). Every change, by dragging, clicking, the mouse wheel, or the keyboard, is set on the arm at once and saved as this arm's speed in the [configuration file](../api/config.md). A speed set with `motion_params` in a script is saved in the same way. When the panel connects to an arm, it sets the arm's saved speed. Scripts running on the same arm use the speed, and the slider follows changes made by scripts.
- JUMP parameters: lift height and Z limit.
- Home and Clear Alarm buttons. Home works also during an alarm, as in DobotLab: the arm homes without an alarm message, and the alarms are cleared when homing ends. The controls are disabled until homing ends. If an alarm comes back after clearing, Clear Alarm shows the alarm and its remedy, and the alarm stays active.
- End-effector controls for the suction cup and gripper. They act at once, also while a script moves the arm.
- Connection indicator: *Connected* only while the arm answers. The panel checks the arm every 2 seconds, before every action, and when reading the pose fails. If the arm does not answer, the panel shows *Disconnected* at once, with a *Reconnect* button, and says what to check; nothing is sent to the arm. If the arm answers again, the panel shows *Connected* and sets the arm's saved speed. After 3 checks in a row without an answer, the panel closes its connection; *Reconnect* opens it again.
- Alarm banner: one short line per active alarm, saying what happened and what to do. With `--dev`, the banner and the alarm messages show the alarm names, codes, and remedies, and the raw alarm bytes.

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
