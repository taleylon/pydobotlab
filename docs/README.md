# pydobotlab

Python control for the Dobot Magician. pydobotlab implements the 28 Python functions of the [DobotLab Magician manual](https://cdn.release.dobot.cc/dobotlab-doc/dobotlab/coding-manual-en/20260205/Dobot%20Magician/Dobot%20Magician.html) with the same names and arguments, and adds waiting and alarm handling, command batching, and pose streaming. All ten `ptp` modes are supported. See [DobotLab compatibility](api/dobotlab.md).

It communicates over serial with `pyserial` using the [Dobot Communication Protocol V1.1.5](Dobot-Communication-Protocol-V1.1.5.pdf). No vendor library or DobotStudio installation is required.

A script and the optional desktop control panel can control the same arm at the same time. A simulator allows use without hardware.

```bash
python -m pip install pydobotlab
# Optional desktop control panel:
python -m pip install "pydobotlab[gui]"
```

[Get started](getting-started/install.md){ .md-button .md-button--primary }
[View on PyPI](https://pypi.org/project/pydobotlab/){ .md-button }

## Contents

1. [Getting Started](getting-started/install.md): installation, connecting to an arm, a first program, and the simulator.
2. [User Guide](guide/workspace.md): workspace, motion patterns, alarm recovery, and pose streaming.
3. [API Reference](api/overview.md): every public class, method, and function.
4. [Control Panel & Broker](panel/overview.md): the PySide6 panel and the TCP broker that lets the panel and a script share one arm.
5. [Protocol Reference](protocol/frame-format.md): frame format, control byte, command IDs, and the method-to-command mapping.

The [table of contents](SUMMARY.md) lists every page.

## Architecture

```
   ┌───────────────────────────────┐    ┌────────────────────────────┐
   │    script  (Magician API)     │    │   ControlPanel (PySide6)   │
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
                       │    SerialTransport  │   
                       └──────────┬──────────┘
                                  ▼
                       ┌─────────────────────┐
                       │  Dobot V1.1.5 wire  │   
                       └─────────────────────┘
```

Scripts and the panel both use the `Magician` class. While the panel is running, the broker relays their commands so that both can drive one arm. Otherwise `Magician` opens the serial port directly.

## References

- [Dobot Communication Protocol V1.1.5](Dobot-Communication-Protocol-V1.1.5.pdf)
- [Dobot Magician V2 User Guide (DobotLab-based) V2.3.1](Dobot-Magician-V2-User-Guide-V2.3.1.pdf)
- [Dobot Magician product page](https://www.dobot-robots.com/products/education/magician.html)
- [Source repository](https://github.com/taleylon/pydobotlab)
