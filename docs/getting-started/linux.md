# Linux setup

Opening the arm's serial port on Linux requires membership in the group that owns the device. The `brltty` service can also hold the port. The commands below are for Ubuntu and Debian.

## Port names

The arm appears as `/dev/ttyUSB0` or `/dev/ttyACM0`, depending on the kernel driver.

| Path | Driver | Adapter |
|---|---|---|
| `/dev/ttyUSB0` | `ch341` | WCH CH340 USB-to-serial adapter. |
| `/dev/ttyACM0` | `cdc_acm` | Built-in USB CDC ACM device. |

Discovery probes every serial port, so either name works. Both drivers are part of the mainline kernel and load automatically. To list the ports and the driver in use:

```bash
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
udevadm info -q all -n /dev/ttyACM0 | grep -E 'ID_VENDOR|ID_MODEL|ID_USB_DRIVER'
```

If no port appears, check that the driver is loaded and what the kernel logged when the arm was connected:

```bash
lsmod | grep -E '^ch341|^cdc_acm'
sudo dmesg --human | tail -30 | grep -iE 'ch341|cdc_acm|tty(USB|ACM)'
sudo modprobe ch341    # or cdc_acm
```

## Permissions

The device is owned by the `dialout` group (`uucp` on Arch Linux). Add the current user to the group, then log out and back in, because group membership is read at login:

```bash
sudo usermod -aG dialout $USER
groups | grep dialout     # after logging in again
```

Without membership, `connect` raises [`DobotPermissionError`](../api/errors.md#dobotpermissionerror), and the panel shows the same message for the port:

> `Permission denied for /dev/ttyACM0: your user is not in the 'dialout' group. Run: sudo usermod -aG dialout $USER then log out and back in (or restart).`

## Busy port

A busy port is reported as `port '/dev/ttyACM0' is busy`. If no other program holds the port, `brltty`, the Braille display service installed with Ubuntu Desktop, may have claimed the device. Stop and disable it:

```bash
sudo systemctl stop brltty
sudo systemctl mask brltty
```

To restore it, run `sudo systemctl unmask brltty && sudo systemctl start brltty`.

To keep `brltty` running and exclude only the arm, add a udev rule in `/etc/udev/rules.d/85-brltty-no-dobot.rules`:

```text
SUBSYSTEMS=="usb", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", ENV{BRLTTY_DEVICE}="-"
```

Then run `sudo udevadm control --reload-rules && sudo udevadm trigger`.

## Selecting a port

```python
from pydobotlab import Magician

Magician()  # automatic selection
Magician(port="/dev/ttyACM0")
```

The example scripts accept the port as an argument or with `-p` / `--port`:

```bash
python examples/smoke_test.py /dev/ttyACM0
python examples/smoke_test.py --port /dev/ttyACM0
```

## Diagnosing connection problems

[`discover_with_diagnostics`](../api/discovery.md#discover_with_diagnostics) returns the arms found and the ports that were rejected, with a reason for each:

```python
from pydobotlab import discover_with_diagnostics

found, failures = discover_with_diagnostics()
print("found:", found)
for failure in failures:
    print(failure.port, failure.reason, failure.detail)
```

The reason is one of `permission`, `busy`, `no_reply`, or `other`. See [`ProbeFailure`](../api/discovery.md#probefailure).

To check each layer separately:

```bash
lsusb | grep -i -E '1a86|dobot|ch340'                                    # the OS sees the device
python3 -c "import serial; serial.Serial('/dev/ttyACM0', 115200).close()"  # the user can open it
```

| Result | Cause |
|---|---|
| `lsusb` shows no device | Cable, power, or the arm. |
| `permission denied` when opening | The user is not in the `dialout` group. |
| `device or resource busy` | Another program or `brltty` holds the port. |
| Opens, but discovery finds nothing | The port belongs to another device, or the arm is not responding. |

## Qt libraries

On a minimal Ubuntu installation, `import PySide6.QtWidgets` may fail with a missing `libEGL.so.1` or `libOpenGL.so.0`. Install the system libraries:

```bash
sudo apt install libegl1 libopengl0
```
