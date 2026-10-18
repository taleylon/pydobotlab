# Running the panel

```bash
pydobotlab-panel
```

`python -m pydobotlab.panel` is equivalent. Both require the `gui` extra (see [Installation](../getting-started/install.md)).

On launch, the panel:

1. Starts a [broker](broker.md) on `127.0.0.1:8765` unless one is already running.
2. Discovers arms as [`discover_with_diagnostics`](../api/discovery.md#discover_with_diagnostics) does.
3. Opens the hub window.

Select an arm and click *Open Control Panel*. Each arm has its own window.

## Options

| Option | Default | Description |
|---|---|---|
| `--simulator`, `-s` | off | Use [simulated arms](../getting-started/simulator.md) instead of hardware. |
| `--simulator-arms N` | `2` | Number of simulated arms. Applies with `--simulator`. |
| `--dev` | off | Show each arm's port, alarm names, codes, and raw bytes, full error details, and the ports tried when no arm is found. |
| `--create-shortcut` | off | Create a [desktop shortcut](#shortcut) for the panel, then exit. |

```bash
pydobotlab-panel --simulator --simulator-arms 3
```

## Desktop shortcut {#shortcut}

```bash
pydobotlab-panel --create-shortcut
```

Creates shortcuts that start the panel with the Python installation they were created from, for example a virtual environment or a system-wide installation.

| System | Shortcuts |
|---|---|
| Windows | Desktop and Start menu. |
| Linux | Desktop and application menu. If the desktop icon shows a warning, right-click it and choose *Allow Launching*. |
| Linux, with `sudo` | Application menu of every user, in `/usr/local/share/applications`. Each user can add a desktop icon by running the command without `sudo`. |

After the Python installation moves, run the command again. To remove a shortcut, delete it; on Linux, the menu entry of a user is `~/.local/share/applications/pydobotlab-panel.desktop`.

## Connection

Opening a control panel connects to the arm through the broker, starts the firmware queue without clearing it, and starts a [pose stream](../api/pose-stream.md) for the readout. Closing the window disconnects it from the arm and leaves the queue unchanged. The broker closes the port when its last client disconnects.

## Running scripts {#scripts}

Start the panel before a script, and quit it after the script ends. A script connects through the panel's broker. When the panel is not running, [`Magician.connect`](../api/magician.md#connect) raises [`DobotConnectionError`](../api/errors.md#dobotconnectionerror).

```bash
pydobotlab-panel          # terminal 1
python my_script.py       # terminal 2
```

- The arm's control panel window does not need to be open. Opening or closing it does not affect a running script.
- The panel's pose readout updates while the script moves the arm.
- Quitting the panel disconnects the connected scripts; their next command raises `DobotConnectionError`. The hub asks for confirmation while scripts are connected.
- A script created with `Magician(require_panel=False)`, or run where the control panel is not installed, opens the serial port directly when the panel is not running. The panel cannot open that arm until the script ends.

`examples/two_dobots_with_panels.py` drives two arms from a script while one control panel is open for each.

## Troubleshooting

- **No arms listed.** The hub says why when the cause is known: a permission problem, or a busy port. With `--dev`, it lists each port that could not be opened, with the reason (a permission problem, `port is busy`, or `couldn't open`), and the ports that answered, but not as a Dobot Magician, under *Other devices (n)*. On Linux, see [Linux setup](../getting-started/linux.md). `python -m serial.tools.list_ports` shows the ports the operating system reports.
- **Port busy.** Another program holds the port: another panel, DobotStudio, or a script that opened the port directly before the panel started. Close it, then click *Refresh*. A process that has exited does not hold the port.
