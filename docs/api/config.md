# Configuration

pydobotlab reads its default settings from a configuration file. Each user has their own copy, created with the default values on first use. The settings cover the serial connection, the broker, discovery, the control panel, the arms' speeds, and the simulator, so they can be changed in one place. Each arm's speed is saved there, by serial number, when it is set in the control panel or with [`motion_params`](speed.md#motion_params); an arm without a saved speed uses the default speed. The file also holds the [reference bounds of the workspace](../guide/workspace.md#reference-bounds).

A value passed as an argument overrides the file. An invalid file raises [`DobotConfigError`](errors.md#dobotconfigerror).
