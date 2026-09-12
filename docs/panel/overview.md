# Control Panel — Overview

`pydobotlab-panel` is the PySide6 control-panel GUI. It replaces the right-hand "Arm Control Panel" of the official DobotStudio / DobotLab desktop app and adds two things the official tool didn't have:

1. **A live pose readout** that updates while a Python script is running (driven by a [pose stream](../api/pose-stream.md)).
2. **A broker** that lets the panel and your script share one arm at the same time.

The panel is a soft dependency — install PySide6 if you want it, skip it if you don't:

```bash
pip install PySide6
```

## What's on screen

* **Hub window** — lists every connected arm. Each row has a "Connect" button that opens (or re-opens) a per-arm Control Panel.
* **Control Panel** *(one per arm)* — the actual driver UI:
  * Live X/Y/Z/R + J1..J4 readout, refreshed at ~50 Hz.
  * Coord-mode and Joint-mode JOG pads (X+/X−/Y+/Y−/Z+/Z−/R+/R−, plus J1..J4).
  * Speed slider (drives both PTP and JOG ratios — see [`motion_params`](../api/speed.md#motion_params-property-tuplefloat-float) / [`set_jog_common_params`](../api/speed.md#set_jog_common_paramsvel_ratio-acc_ratio-int)).
  * JUMP-mode parameter card (height, zlimit).
  * Home / Clear Alarm buttons.
  * Alarm banner: shows every active alarm on its own line as `"{TAG}: {explanation + how to fix}"`.
  * End-effector controls (suction cup, gripper).

## What runs where

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

Each `ControlPanel` owns its own `Magician` and its own `PoseStreamer` (a `QThread` polling `get_pose` and emitting Qt signals). All panels connect through the broker so a parallel script can share each arm.

## Pages in this section

* [Running the panel](running.md) — installation, command-line flags, simulator mode.
* [The DobotBroker](broker.md) — the TCP server that fans out one serial port to many clients.
