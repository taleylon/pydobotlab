# Configuration

pydobotlab reads its default settings from a configuration file. Each user has their own copy, created with the default values on first use. The settings cover the serial connection, the broker, discovery, the control panel, and the simulator, so they can be changed in one place. The file also holds the [reference bounds of the workspace](../guide/workspace.md#reference-bounds).

A value passed as an argument overrides the file. An invalid file raises [`DobotConfigError`](errors.md#dobotconfigerror).
