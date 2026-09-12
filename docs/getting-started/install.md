# Installation

`pydobotlab` is a pure-Python package. The only hard runtime dependency is `pyserial`. The control panel adds a soft dependency on `PySide6` (Qt for Python).

## Make a virtual environment

We strongly recommend installing into a virtual environment so the package and its dependencies don't conflict with anything else on your machine.

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

You'll know the venv is active because your shell prompt shows `(.venv)`.

## Install pydobotlab

Requires Python 3.10 or newer. Install the published package from PyPI:

```bash
python -m pip install pydobotlab
```

To work from source before the first release, run
`python -m pip install -e .` from the project root (where `pyproject.toml` lives).

This installs the library plus its console scripts (`pydobotlab-panel`).

If you want the **control panel GUI** (recommended for students), install the GUI extra:

```bash
python -m pip install "pydobotlab[gui]"
```

The library itself works without PySide6 - it's only required for the panel.

## Verify the install

```bash
python -c "import pydobotlab; print(pydobotlab.__version__)"
```

Should print a version number (e.g. `0.1.0`).

## Connect the arm (optional, can come later)

Plug a real Magician into a USB port and check that your OS can see it:

* **macOS / Linux**: `ls /dev/tty.usbserial-* /dev/ttyUSB* /dev/ttyACM*` - you should see the device. Note: on Ubuntu the Magician often shows up as `/dev/ttyACM0` (the CDC ACM driver) rather than `/dev/ttyUSB0`; both work. See [Linux setup](linux.md) for the dialout/brltty fixes you'll need first.
* **Windows**: open Device Manager → Ports (COM & LPT) - note the COM number (e.g. `COM3`).

If you don't have a real arm yet, the [simulator](simulator.md) lets you run everything in this guide without one.

## Next

* [Connecting to an arm →](connect.md)
