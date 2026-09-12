# pydobotlab - User Guide

Python control for the **Dobot Magician**, with full coverage of the 28 Python
API entries in the [official DobotLab Magician manual](https://cdn.release.dobot.cc/dobotlab-doc/dobotlab/coding-manual-en/20260205/Dobot%20Magician/Dobot%20Magician.html).
Use the documented function names and arguments for motion, I/O, sensors,
end-effectors, the slideway, and the conveyor.

All ten `ptp` modes are supported. Extended control adds `move_to` with waiting,
timeouts, and alarm handling, command batching, and live pose streaming. Run Python scripts
and the optional desktop control panel separately or in parallel. A simulator
supports working without hardware.

Communicates over serial using `pyserial` and the
[Dobot Communication Protocol V1.1.5](https://download.dobot.cc/product-manual/dobot-magician/pdf/en/Dobot-Communication-Protocol-V1.1.5.pdf);
no vendor DLL or DobotStudio installation is required.

[See all supported DobotLab functions](api/dobotlab.md).

Browse the guide using the sidebar, search for an API method, or use the [table of contents](SUMMARY.md). The Markdown source lives in the [GitHub repository](https://github.com/taleylon/pydobotlab/tree/main/docs). If you're new, start with [Getting Started](getting-started/install.md). If you already know the SDK and just want to look up a command, jump to the [API Reference](api/overview.md).

```bash
python -m pip install pydobotlab
# Optional desktop control panel:
python -m pip install "pydobotlab[gui]"
```

[Get started](getting-started/install.md){ .md-button .md-button--primary }
[View on PyPI](https://pypi.org/project/pydobotlab/){ .md-button }

## What's in this guide

The guide is split into four parts:

1. **[Getting Started](getting-started/install.md)** - installing the package, connecting to an arm, running your first program, and the simulator.
2. **[API Reference](api/overview.md)** - every public function on `Magician`, grouped by what it does (motion, alarms, queue, end-effectors, I/O, ...). Each entry says what it does, what it returns, and which Dobot protocol command it sends.
3. **[Control Panel & Broker](panel/overview.md)** - the PySide6 GUI, the multi-arm hub, and the TCP broker that lets the panel and a script share one arm.
4. **[Protocol Reference](protocol/frame-format.md)** - the wire-level Dobot protocol: frame format, control byte, the full `CommandID` table, and how each ID maps back to a `Magician` method.

## How the layers fit together

```
   ┌───────────────────────────────┐    ┌────────────────────────────┐
   │  your script  (Magician API)  │    │   ControlPanel (PySide6)   │
   └───────────────┬───────────────┘    └──────────────┬─────────────┘
                   │                                   │
                   └──────────────┬────────────────────┘
                                  ▼
                       ┌─────────────────────┐
                       │     DobotBroker     │   TCP 127.0.0.1:8765
                       │  (per-port refcnt)  │   (auto-spawned by panel)
                       └──────────┬──────────┘
                                  ▼
                       ┌─────────────────────┐
                       │    SerialTransport  │   115200 8N1
                       └──────────┬──────────┘
                                  ▼
                       ┌─────────────────────┐
                       │  Dobot V1.1.5 wire  │   AA AA  len  id  ctrl  …  cks
                       └─────────────────────┘
```

The script-side and panel-side both speak through the same `Magician` class. When the panel is open the broker mediates so both can drive one arm; when there's no panel, `Magician` opens the serial port directly.

## Quick links

- Source code on disk: `pydobotlab/` (library), `pydobotlab/panel/` (GUI), `examples/`.
- Protocol PDF reference: [Dobot Communication Protocol V1.1.5](https://download.dobot.cc/product-manual/dobot-magician/pdf/en/Dobot-Communication-Protocol-V1.1.5.pdf) - the canonical source for command IDs and parameter layouts. See the [Protocol Reference](protocol/frame-format.md) for packet details.
- Magician feature page: [Dobot Magician - features](https://www.dobot-robots.com/products/education/magician.html).
