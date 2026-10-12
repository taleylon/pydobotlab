# Installation

pydobotlab requires Python 3.11 or newer. Its only required dependency is `pyserial`. The control panel also requires `PySide6`.

## Create a virtual environment

macOS and Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## Install

```bash
python -m pip install pydobotlab
```

To use the control panel (`pydobotlab-panel`), install the `gui` extra:

```bash
python -m pip install "pydobotlab[gui]"
```

To install from a source checkout, run `python -m pip install -e .` in the directory that contains `pyproject.toml`.

## Verify

```bash
python -c "import pydobotlab; print(pydobotlab.__version__)"
```

The command prints the installed version.

## Check that the arm is visible

- macOS and Linux: run `ls /dev/tty.usbserial-* /dev/ttyUSB* /dev/ttyACM*`. The arm appears as `/dev/ttyUSB0` or `/dev/ttyACM0`. See [Linux setup](linux.md) for the required permissions.
- Windows: open Device Manager, then Ports (COM & LPT), and note the COM number, for example `COM3`.

Without an arm, use the [simulator](simulator.md).

## Next

- [Connecting to an arm](connect.md)
