# Changelog

All notable changes to pydobotlab. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.2.1] - 2026-10-17

### Changed (breaking)

- Alarm codes and names follow the Dobot Magician ALARM Description V1.0.1, now hosted with the documentation. Several codes had the wrong name: for example `0x43`, reported when J2 is below its range, is `LIMIT_NEG_J2` (was `LIMIT_POS_J4`), and `0x50` to `0x53` are lost-step alarms (were negative joint limits).
  - Planning and motion alarms: `PLAN_INVERSE_SINGULARITY`, `PLAN_INVERSE_CALCULATION` (target out of the workspace), `PLAN_INVERSE_LIMIT`, `PLAN_DATA_REPEAT`, `PLAN_ARC_INPUT_PARAMETER`, `PLAN_JUMP_PARAMETER`, `MOVE_INVERSE_SINGULARITY`, `MOVE_INVERSE_CALCULATION`, and `MOVE_INVERSE_LIMIT` replace the previous `PLAN_*` and `KINEMATIC_*` names.
  - New: `LIMIT_POS_PARALLELOGRAM` and `LIMIT_NEG_PARALLELOGRAM` (`0x48`, `0x49`): the rear arm and forearm stretched or folded to their limit.
  - Removed: `OTHER_LIMIT_TRIGGERED_J1_J2` and the codes `0x60` to `0x63`, which are not in the document.
  - Codes without a name are labelled by group and code, for example `LIMIT_0x4A`.
  - The remedy in each alarm message follows the document; for example, a joint-limit alarm says which way to jog the joint.
- A lost-step alarm raises `DobotLostStepError` (previously `DobotKinematicError`).
- `set_home()` works also during an alarm, as in DobotLab: the arm homes, and the alarms are cleared when homing ends. It raises only if an alarm comes back after clearing.

### Added

- Control panel:
  - Arms are named *Dobot Magician 1*, *Dobot Magician 2*, and so on, in the hub and in their control panel windows, numbered in the order they are found.
  - `pydobotlab-panel --dev` shows each arm's port, the alarm names, codes, remedies, and raw alarm bytes, and full error details.
  - Alarms are shown as one short line each: what happened and what to do. The text is in `pydobotlab/panel/panel.toml`.
  - In the hub, a line separates the Dobot Magicians from *Other devices (n)*.

### Changed

- Control panel:
  - Home works during an alarm, as in DobotLab, and shows no alarm message. The controls are disabled until homing ends.
  - The jog pads work during an alarm, as in DobotLab: the arm refuses a jog it cannot make, and a joint-limit alarm ends by itself when the joint is jogged back off the limit.
- The simulator reports `PLAN_INVERSE_CALCULATION` for an unreachable target, as the arm does, and homes also during an alarm.

### Fixed

- Closing the control panel while a script was connected through it left the panel's process running and the arm's port busy until the script disconnected. The panel now closes at once, and the script's next command raises `DobotConnectionError`.
- The hub cut a long permission message short. It is now explained in a box above the list, wrapped to the window width.
- Alarm codes without a name, such as the parallelogram limit, were shown as raw codes in the panel.

### Documentation

- Alarm reference: the meaning of each code and how each alarm ends, from the ALARM Description, and a table of code ranges with their exception classes.
- The README and the examples call `set_home()` without `clear_alarm()` first, so they also start from an arm switched on in an alarm.
- `DobotBroker.stop` and the DobotLab differences describe the new behavior.
- Corrected: the simulator page gave `--arms` instead of `--simulator-arms`.

## [0.2] - 2026-10-12

### Changed (breaking)

- The DobotLab functions behave as in DobotLab, with the same signatures. All 20 setters (`ptp`, `set_r`, `set_home`, `wait`, `motion_params`, `jump_params`, `set_multiplexing`, `set_pwm`, `set_do`, `set_endeffector_suctioncup`, `set_endeffector_gripper`, `set_infrared_sensor`, `set_color_sensor`, `set_ptpl_params`, `set_ptpwithl_cmd`, `set_converyor`, `set_lost_step_cmd`, `set_device_withl`, `set_lost_step_params`, `clear_alarm`) wait until the arm has executed the command and return `True`. `set_endeffector_laser` waits too. They previously returned the firmware queue index; use `move_to(..., wait=False)` with `wait_for` where an index is needed.
- An alarm reported by the arm raises an exception at the command that meets it, which stops the program. An alarm left over from earlier stops the next command, since the arm refuses to work until the alarm is cleared. Commands still queued are discarded, so clearing the alarm does not resume them. Previously only `wait_for`, `wait_idle`, `move_to`, and `set_home` checked alarms, and only motion alarms.
- `set_home()` takes no arguments (`wait`, `timeout`, and `raise_on_alarm` were removed).
- `clear_alarm()` takes no arguments (`verify` and `settle` were removed). It always reads the alarms again 0.2 s after clearing; if an alarm is back because its cause is still present, the alarm stays active and its exception is raised.
- `batch()`: inside the block the DobotLab functions only queue their command; the end of the block runs the queue and waits, raising on an alarm. If the block raises, the queued commands are discarded.
- `disconnect()` clears the firmware queue and leaves it running for the control panel or the next program, instead of pausing it.
- `wait_for`, `wait_idle`, and `move_to` raise for every alarm code, with the exception of the alarm's group. `jog()` still works while an alarm is active, so a joint can be jogged away from its limit.
- Python 3.11 or newer is required.

### Added

- Exceptions for each alarm group: `DobotKinematicError` (planning, kinematic, and joint-limit alarms) and the new `DobotOverspeedError`, `DobotLostStepError`, and `DobotSystemAlarmError`. All derive from `DobotAlarmError`; other codes raise `DobotAlarmError`. The class follows the active alarm with the lowest code, and the message lists every active alarm with a remedy.
- `DobotPermissionError` (a `DobotConnectionError`): the operating system denied access to the serial port. The port itself is checked, and the message names the fix: join the device's group (for example `dialout`) and log in again; log out and back in when the group was added after the session started; check the device permissions and SELinux or AppArmor when access is still denied; or check the group's read and write permission on the device.
- Configuration file: one file holds the default settings for the serial connection, the broker, discovery, the control panel, and the simulator, and each user gets a copy on first use. Arguments in code override it; a parameter left as `None` uses the configured value. The broker host stays configurable. If the user's copy cannot be created, the shipped defaults are used. `DobotConfigError` reports an unknown setting or a value of the wrong type, naming the file and the setting.
- Reference bounds of the workspace in the configuration file (`[workspace]`: minimum and maximum distance from the base axis, lowest and highest Z), from the Dobot Magician user guide. Programs can check targets against them; they can be narrowed, not widened. The arm and pydobotlab do not check moves against them.
- `Magician.execute_command()`: queue a command and wait until the arm has executed it.
- `Magician(verbose=True)`: `connect()` prints `[pydobotlab] Connected to <port>.`, with `(shared through the panel)` when connected through the broker, or `[pydobotlab] Failed to connect: <reason>` to standard error before raising. `verbose=False` silences both.
- Serial ports still open when the program exits are closed by an exit hook, so exiting without `disconnect()` releases the port.
- `start_pose_stream(on_error=...)`: a streak of failures is reported once, to `on_error` or as `[pydobotlab] Pose stream failing: ...` on standard error, followed by `Pose stream recovered.` when it works again.
- Control panel:
  - Round jog pads laid out as in DobotLab, with hover and pressed highlighting, replacing the round buttons. X/Y pad: X+ top, X- bottom, Y- left, Y+ right (previously Y+ top, X+ right). Z/R pad: Z+ top, Z- bottom, R- left, R+ right. J1/J2 and J3/J4 pads: J1- and J3- top left, J1+ and J3+ top right, J2- and J4- bottom left, J2+ and J4+ bottom right. Disabling a pad while it is pressed stops the jog.
  - Connection watchdog: the window shows *Disconnected*, with a *Reconnect* button, after 3 failed checks in a row. A single failed check shows `checking connection...`.
  - The speed slider takes the arm's current speed when the panel opens or reconnects, follows speed changes made by scripts, and sets the jog speed too. The speed is stored in the arm, so scripts on the same arm share it.
  - Speed, JUMP parameters, and end-effector buttons act at once, also while a script moves the arm.
  - Clear Alarm confirms that the alarm stays cleared; otherwise it shows the alarm and its remedy, and the alarm stays active. Home shows the active alarm and its remedy when it cannot run.
  - `STOP FAILED - the arm may still be moving: ...` in the status bar when stopping a jog fails, and pose stream errors in the status bar.
  - The pydobotlab version (`pydobotlab v0.2`) at the bottom right of the hub and of each control panel window.
  - The hub lists the ports that answer, but not as a Dobot Magician, under *Other devices (n)*, with the device description from the operating system. The group is collapsed by default, a click expands it, and it is shown also when there are none. Only Dobot Magicians can be opened.
- Broker:
  - A failed request is answered with its cause (timeout, connection, protocol, or internal error), and the client raises the matching exception. The connection stays open after a reported failure.
  - Attaching to a port answers busy and permission failures with their own replies, instead of "not found" for every failure.
  - TCP keepalive on client connections.
- Simulator:
  - Reachability follows the arm's joint ranges (base -90° to +90°, rear arm 0° to 85°, forearm -10° to +90°) and arm lengths (135 mm and 147 mm) from the Dobot Magician user guide V2.3.1. An unreachable point-to-point target sets `PLAN_MOTION_TARGET_OUT_OF_WORKSPACE`.
  - A command queue as on the arm: commands run in order, `wait` pauses for its duration, settings take effect when they reach the head of the queue, and the queue stops while an alarm is active. Starting, stopping, force-stopping, and clearing the queue are modelled.
  - Speeds, tick rate, and the default number of arms come from the configuration file.

### Changed

- The control panel's hub and window title show only the port name; the serial number is no longer read when the panel connects. `discover()` still returns `DiscoveredDobot.serial_number`.
- A busy port is reported as `port 'COM3' is busy`, or `port 'COM3' is busy (already open in this program)` when the same program opens it twice. The advice about brltty is gone from the panel.
- `ProbeFailure.reason` follows the type of the exception rather than its text. `Magician()` without a port reports a permission problem or busy ports instead of a generic "nothing answered".
- `discover`, `discover_with_diagnostics`, `find_free_port`, and `is_dobot` identify a Dobot Magician by its replies to three read requests, in the formats of the Communication Protocol V1.1.5: `GetDeviceSN` (command ID 0 and the serial number), `GetDeviceVersion` (command ID 2 and three version bytes), and `GetPose` (command ID 10 and eight finite floats). The requests do not move the arm or change its state. A device that answers otherwise, or echoes the request, is not listed and is reported with reason `"no_reply"`. Previously any well-formed frame in reply to `GetDeviceSN` was accepted.
- The panel's hub explains a permission problem once instead of once per port, and shows `port is busy` for busy ports.
- The panel's hub names the device in its messages, for example `No Dobot Magician devices were found.`
- The control panel window opens at 880 x 760.

### Fixed

- A missing serial-port permission on Linux was reported as a busy port.
- Clients connected through the broker were dropped after about 5 s without a request. The broker now waits indefinitely between requests and drops only a request that stalls halfway.
- The broker closed the connection without a reason on any failure.
- A late reply to a timed-out request could be read as the reply to the next request, on the serial line and through the broker.
- Opening or reconnecting the control panel reset the arm's speed to 50 %.
- The panel's hub listed its results twice when a scan was requested during another scan, for example when a control panel closed; the two scans also competed for the same ports. A scan requested during another now runs after it.
- `jog_stop()` hid a failed retry; it now raises, since the arm may still be moving.
- Pose stream failures were hidden.
- Simulator: a command that does not move finished before the moves queued ahead of it, and queued moves replaced each other.

### Removed

- The simulator's own workspace settings, which were not the arm's real limits and never affected a real arm.

### Documentation

- The API reference was rewritten: a summary table per page and one entry per member with its signature, parameters, return value, exceptions, and an example. New pages: Magician, Accessories, Low-level commands, Broker, Simulator, and Configuration.
- New User Guide: motion patterns, alarms and recovery, pose streaming, and the workspace (specifications, coordinate system, and the workspace figures of the Dobot user guide).
- Every page was revised for clear, concise wording.
- Examples use `ptp` with the mode written out and named, and no longer wait after DobotLab functions.
- The Dobot Magician V2 User Guide V2.3.1 and the Dobot Communication Protocol V1.1.5 are hosted with the documentation.
- Corrected: the command sequence of `batch()`, the missing `set_endeffector_laser` command in the method-to-command table, and the claim that homing clears most alarms.
- Linux setup: the new permission messages; busy ports and brltty only when nothing else holds the port.
- Discovery: the requests and replies that identify a Dobot Magician. Control panel: the hub's *Other devices (n)* group and the version shown in each window.

### Development

- CI tests Python 3.11 to 3.14. The only dependency is `pyserial`; the configuration file is read with the standard `tomllib`.
- Tests check that every public name is documented in the API reference, and that the installed package includes the configuration file.

## [0.1.0.1] - 2026-09-13

### Added

- `PTPMode.JUMP_MOVL_XYZ` (mode 9).
- A DobotLab compatibility page in the documentation.

### Fixed

- `set_color_sensor` and `set_infrared_sensor` send the enable flag before the port, as the protocol requires.
- `get_color_sensor` sends no port.
- `set_device_withl` and `set_lost_step_params` are sent as immediate commands.

## [0.1.0] - 2026-09-12

First release: the Python functions of the DobotLab Magician manual over serial, the firmware command queue, alarms, pose streaming, port discovery, the broker, the PySide6 control panel, and the simulator.

[0.2.1]: https://github.com/taleylon/pydobotlab/compare/v0.2...v0.2.1
[0.2]: https://github.com/taleylon/pydobotlab/compare/v0.1.0.1...v0.2
[0.1.0.1]: https://github.com/taleylon/pydobotlab/compare/v0.1.0...v0.1.0.1
[0.1.0]: https://github.com/taleylon/pydobotlab/releases/tag/v0.1.0
