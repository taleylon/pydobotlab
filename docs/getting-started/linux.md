# Linux setup (Ubuntu / Debian)

The Magician works the same on Linux as on Windows once a few OS-specific quirks are out of the way. If you've just plugged your arm into Ubuntu for the first time and `pydobotlab-panel` is showing "no Dobots found" — this page is for you.

## TL;DR

```bash
# 1. Put yourself in the dialout group (one-time).
sudo usermod -aG dialout $USER

# 2. Stop the brltty daemon if it's installed — it grabs CDC/ACM devices.
sudo systemctl stop brltty
sudo systemctl mask brltty   # optional, prevents it from auto-starting

# 3. Log out and back in for the group change to take effect.
exit
```

Then plug the arm back in, open a new shell, and run:

```bash
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
```

You should see one device. Either path works — the library is happy with both.

## Why the arm sometimes appears as `/dev/ttyACM0` instead of `/dev/ttyUSB0`

Both are the OS-side name of the same serial port; they differ only in which kernel driver claimed the USB device:

| Path           | Driver     | When it shows up |
|----------------|------------|------------------|
| `/dev/ttyUSB0` | `ch341`    | Magicians with a WCH CH340 USB-to-UART adapter (most kits seen in the wild). |
| `/dev/ttyACM0` | `cdc_acm`  | Magician revisions with a built-in USB CDC ACM device (some newer / educational kits). Also any time a different kernel driver wins the race for the same device. |

It is **not** a problem and you don't need to switch it back. pydobotlab's discovery code enumerates *every* serial port `pyserial` sees and probes each one, so a ttyACM-attached arm is found the same way a ttyUSB-attached arm is. Same on the panel side.

If you'd like to confirm which path your kernel is using:

```bash
udevadm info -q all -n /dev/ttyACM0 2>/dev/null | grep -E 'ID_VENDOR|ID_MODEL|ID_USB_DRIVER'
udevadm info -q all -n /dev/ttyUSB0 2>/dev/null | grep -E 'ID_VENDOR|ID_MODEL|ID_USB_DRIVER'
```

## Do I need to install the `ch341` driver?

**Almost always: no.** Both relevant drivers have shipped in mainline Linux for over a decade and Ubuntu auto-loads them when the device appears. Specifically:

* `ch341` — for Magicians whose USB cable has a WCH CH340 chip (the most common kit). In the kernel since 2.6.x.
* `cdc_acm` — for Magicians that present as a USB CDC ACM device directly (newer revisions, no CH340 chip). In the kernel since the earliest days.

You'd only need to install something manually if either:

1. You're on a stripped-down distro that ships without USB-serial modules (very rare), **or**
2. You have a WCH chip revision newer than the one in the mainline driver (CH343 / CH9102 — *not* the standard CH340 in the Magician).

For the Magician you should be in case (0): the driver is already on disk, the kernel auto-loaded it when you plugged the arm in, and the device showed up as `/dev/ttyUSB0` or `/dev/ttyACM0`.

### Quick sanity check

```bash
# Is the driver module on disk? (One or both should appear.)
modinfo ch341 2>/dev/null | head -3
modinfo cdc_acm 2>/dev/null | head -3

# Is it currently loaded?
lsmod | grep -E '^ch341|^cdc_acm'

# What did the kernel say when you plugged the arm in?
sudo dmesg --human | tail -30 | grep -iE 'ch341|cdc_acm|tty(USB|ACM)'
```

A healthy `dmesg` line after plug-in looks like one of these:

```
usb 1-1: ch341-uart converter now attached to ttyUSB0
cdc_acm 1-1:1.0: ttyACM0: USB ACM device
```

### If the driver actually *isn't* loaded

If `lsmod` shows nothing and your device doesn't appear under `/dev/tty*`, load it manually:

```bash
sudo modprobe ch341    # or: sudo modprobe cdc_acm
```

Plug the cable in again, then check `dmesg` and `ls /dev/tty*`.

### If you truly need WCH's out-of-tree driver

Only relevant for newer WCH chips (CH343, CH9102) that the kernel doesn't yet recognise. The vendor source lives at <https://github.com/WCHSoftGroup/ch341ser_linux>. Build & install:

```bash
git clone https://github.com/WCHSoftGroup/ch341ser_linux.git
cd ch341ser_linux/driver
make
sudo make install
sudo modprobe ch341
```

You will **not** need this for any Magician currently shipping. If you're tempted to try this because the panel can't find your arm, stop and re-check the `dialout` group and `brltty` first — those account for the overwhelming majority of "no Dobots found" reports on Linux.

## "Permission denied" on `/dev/ttyACM0` or `/dev/ttyUSB0`

Linux serial devices are owned by the `dialout` group (Ubuntu, Debian) or `uucp` (Arch). You need to be a member, otherwise opening the device fails with `permission denied`. pydobotlab's panel will now show this explicitly — if you see a line like

> `/dev/ttyACM0    permission denied — try 'sudo usermod -aG dialout $USER' then log out & back in`

that's the fix:

```bash
sudo usermod -aG dialout $USER
# log out and back in (group membership is set at login)
```

After re-login, verify with `groups | grep dialout`.

## "Device or resource busy" — brltty hijacking

`brltty` is a Braille display daemon shipped by default with Ubuntu Desktop. Many CDC/ACM devices (and a *lot* of microcontroller dev boards) match the heuristics it uses to recognise Braille terminals, so it grabs the device the instant you plug it in. The Magician is one of the affected devices.

You'll see this in the panel as

> `/dev/ttyACM0    port busy — close DobotStudio, another panel, or stop brltty: 'sudo systemctl stop brltty'`

Fix:

```bash
sudo systemctl stop brltty
sudo systemctl mask brltty       # disable on boot
```

If you ever use a Braille display, just `sudo systemctl unmask brltty && sudo systemctl start brltty` to bring it back.

A more surgical alternative (keeps brltty running for actual Braille hardware but stops it touching the Magician) is to add a udev rule:

```bash
# /etc/udev/rules.d/85-brltty-no-dobot.rules
SUBSYSTEMS=="usb", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", ENV{BRLTTY_DEVICE}="-"
```

Then `sudo udevadm control --reload-rules && sudo udevadm trigger`.

## Passing a specific port to your script

pydobotlab's `Magician()` accepts the full device path. All of these work:

```python
from pydobotlab import Magician

# auto-pick (default)
Magician()

# explicit path
Magician(port="/dev/ttyUSB0")
Magician(port="/dev/ttyACM0")
```

For the example scripts, the CLI accepts both positional and flag form:

```bash
python examples/smoke_test.py                          # auto-pick
python examples/smoke_test.py /dev/ttyACM0             # positional
python examples/smoke_test.py --port /dev/ttyACM0      # flag
python examples/smoke_test.py -p /dev/ttyACM0          # short flag
```

(If you only see the positional form in older scripts, you can update them the same way — the parser change is just `parser.add_argument("-p", "--port", ...)`.)

## Diagnosing from Python

If you want to know what the library sees without launching the panel:

```python
from pydobotlab import Discovery

hits, failures = Discovery.discover_with_diagnostics()
print("found:", hits)
for f in failures:
    print(f"  rejected {f.port}: {f.reason} — {f.detail}")
```

`failures` is a list of [`ProbeFailure`](../api/discovery.md#probefailure) records, each with `.port`, `.description`, `.reason` (`permission`, `busy`, `no_reply`, or `other`), and the full `.detail` message.

## Still stuck?

A complete sanity check:

```bash
# 1. Is the OS seeing the device at all?
lsusb | grep -i -E '1a86|dobot|ch340'
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null

# 2. Can I open it as my user?
python3 -c "import serial; serial.Serial('/dev/ttyACM0', 115200).close(); print('OK')"

# 3. Does pydobotlab see it?
python3 -c "
from pydobotlab import Discovery
hits, failures = Discovery.discover_with_diagnostics()
print('hits:', hits)
for f in failures: print(' ', f.port, f.reason, f.detail)
"
```

If step 2 fails with `permission denied`, fix the dialout group. If step 2 fails with `device or resource busy`, stop brltty. If step 2 succeeds but step 3 returns nothing in `hits`, the cable/arm is the problem (different serial port, dead arm, missing firmware).

## Qt libraries for the desktop panel

On a minimal Ubuntu installation, the GUI may also need the system OpenGL
libraries, even when running tests with `QT_QPA_PLATFORM=offscreen`:

```bash
sudo apt install libegl1 libopengl0
```

Install these if importing `PySide6.QtWidgets` reports a missing
`libEGL.so.1` or `libOpenGL.so.0` library.
