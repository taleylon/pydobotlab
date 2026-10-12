# Command ID table

Command IDs of the [Dobot Communication Protocol V1.1.5](../Dobot-Communication-Protocol-V1.1.5.pdf) defined in `pydobotlab.CommandID`.

Each row lists the ID in decimal and hexadecimal, the `CommandID` member, and the `Magician` methods that send it. A dash means that no method sends the command. Such commands can be sent with the [low-level methods](#commands-without-a-method).

## Device information

| ID  | Hex  | Symbol | Magician method |
|-----|------|--------|-----------------|
| 0   | 0x00 | `GET_DEVICE_SN`       | [`get_device_serial_number`](../api/magician.md#get_device_serial_number), [`is_dobot`](../api/discovery.md#is_dobot), [`discover`](../api/discovery.md#discover) |
| 1   | 0x01 | `GET_SET_DEVICE_NAME` | [`get_device_name`](../api/magician.md#get_device_name), [`set_device_name`](../api/magician.md#set_device_name) |
| 2   | 0x02 | `GET_DEVICE_VERSION`  | [`get_device_version`](../api/magician.md#get_device_version) |
| 3   | 0x03 | `GET_SET_DEVICE_WITH_L` | [`set_device_withl`](../api/accessories.md#set_device_withl) |
| 4   | 0x04 | `GET_DEVICE_TIME`     | - |
| 5   | 0x05 | `GET_DEVICE_ID`       | - |

## Real-time pose

| ID  | Hex  | Symbol | Magician method |
|-----|------|--------|-----------------|
| 10  | 0x0A | `GET_POSE`     | [`get_pose`](../api/motion.md#get_pose), [`start_pose_stream`](../api/pose-stream.md#start_pose_stream) |
| 11  | 0x0B | `RESET_POSE`   | - |
| 12  | 0x0C | `GET_KINEMATICS` | - |
| 13  | 0x0D | `GET_POSE_L`   | [`get_posel`](../api/accessories.md#get_posel) |

## Alarms

| ID  | Hex  | Symbol | Magician method |
|-----|------|--------|-----------------|
| 20  | 0x14 | `GET_ALARMS_STATE` *(read)* | [`get_alarms`](../api/alarms.md#get_alarms), [`ensure_no_alarms`](../api/alarms.md#ensure_no_alarms), [`get_lost_step_result`](../api/accessories.md#get_lost_step_result) |
| 20  | 0x14 | `CLEAR_ALL_ALARMS_STATE` *(write)* | [`clear_alarm`](../api/alarms.md#clear_alarm) |

> Same ID, different roles - selected by the [`rw` bit](ctrl-byte.md). See [Alarms](../api/alarms.md) for what the 16 mask bytes encode.

## Home

| ID  | Hex  | Symbol | Magician method |
|-----|------|--------|-----------------|
| 30  | 0x1E | `GET_SET_HOME_PARAMS` | - |
| 31  | 0x1F | `SET_HOME_CMD`        | [`set_home`](../api/motion.md#set_home) |
| 32  | 0x20 | `SET_AUTO_LEVELING`   | - |

## Handhold teaching

| ID  | Hex  | Symbol | Magician method |
|-----|------|--------|-----------------|
| 40  | 0x28 | `GET_SET_HHT_TRIG_MODE` | - |
| 41  | 0x29 | `GET_SET_HHT_TRIG_OUTPUT_ENABLED` | - |
| 42  | 0x2A | `GET_HHT_TRIG_OUTPUT` | - |

## Arm orientation

| ID  | Hex  | Symbol | Magician method |
|-----|------|--------|-----------------|
| 50  | 0x32 | `GET_SET_ARM_ORIENTATION` | - |

## End-effector

| ID  | Hex  | Symbol | Magician method |
|-----|------|--------|-----------------|
| 60  | 0x3C | `GET_SET_END_EFFECTOR_PARAMS` | - |
| 61  | 0x3D | `GET_SET_END_EFFECTOR_LASER`  | [`set_endeffector_laser`](../api/end-effectors.md#set_endeffector_laser) |
| 62  | 0x3E | `GET_SET_END_EFFECTOR_SUCTION_CUP` | [`set_endeffector_suctioncup`](../api/end-effectors.md#set_endeffector_suctioncup) |
| 63  | 0x3F | `GET_SET_END_EFFECTOR_GRIPPER`     | [`set_endeffector_gripper`](../api/end-effectors.md#set_endeffector_gripper) |

## JOG

| ID  | Hex  | Symbol | Magician method |
|-----|------|--------|-----------------|
| 70  | 0x46 | `GET_SET_JOG_JOINT_PARAMS`      | - |
| 71  | 0x47 | `GET_SET_JOG_COORDINATE_PARAMS` | - |
| 72  | 0x48 | `GET_SET_JOG_COMMON_PARAMS`     | [`set_jog_common_params`](../api/speed.md#set_jog_common_params), [`get_jog_common_params`](../api/speed.md#get_jog_common_params) |
| 73  | 0x49 | `SET_JOG_CMD`                   | [`jog`](../api/jog.md#jog), [`jog_stop`](../api/jog.md#jog_stop) |
| 74  | 0x4A | `GET_SET_JOG_L_PARAMS`          | - |

## PTP

| ID  | Hex  | Symbol | Magician method |
|-----|------|--------|-----------------|
| 80  | 0x50 | `GET_SET_PTP_JOINT_PARAMS`      | - |
| 81  | 0x51 | `GET_SET_PTP_COORDINATE_PARAMS` | - |
| 82  | 0x52 | `GET_SET_PTP_JUMP_PARAMS`       | [`jump_params`](../api/speed.md#jump_params) |
| 83  | 0x53 | `GET_SET_PTP_COMMON_PARAMS`     | [`motion_params`](../api/speed.md#motion_params), [`get_arm_speed_ratio`](../api/speed.md#get_arm_speed_ratio) |
| 84  | 0x54 | `SET_PTP_CMD`                   | [`ptp`](../api/motion.md#ptp), [`move_to`](../api/motion.md#move_to), [`set_r`](../api/motion.md#set_r) |
| 85  | 0x55 | `GET_SET_PTP_L_PARAMS`          | [`set_ptpl_params`](../api/accessories.md#set_ptpl_params) |
| 86  | 0x56 | `SET_PTP_WITH_L_CMD`            | [`set_ptpwithl_cmd`](../api/accessories.md#set_ptpwithl_cmd) |
| 87  | 0x57 | `GET_SET_PTP_JUMP_2_PARAMS`     | - |
| 88  | 0x58 | `SET_PTP_PO_CMD`                | - |
| 89  | 0x59 | `SET_PTP_PO_WITH_L_CMD`         | - |

## Continuous path (CP)

| ID  | Hex  | Symbol | Magician method |
|-----|------|--------|-----------------|
| 90  | 0x5A | `GET_SET_CP_PARAMS` | [`set_cp_params`](../api/speed.md#set_cp_params) |
| 91  | 0x5B | `SET_CP_CMD`        | [`cp`](../api/motion.md#cp) |
| 92  | 0x5C | `SET_CP_LE_CMD`     | - |

## ARC

| ID  | Hex  | Symbol | Magician method |
|-----|------|--------|-----------------|
| 100 | 0x64 | `GET_SET_ARC_PARAMS`        | - |
| 101 | 0x65 | `SET_ARC_CMD`               | - |
| 102 | 0x66 | `SET_CIRCLE_CMD`            | - |
| 103 | 0x67 | `GET_SET_ARC_COMMON_PARAMS` | - |

## Wait / trigger

| ID  | Hex  | Symbol | Magician method |
|-----|------|--------|-----------------|
| 110 | 0x6E | `SET_WAIT_CMD` | [`wait`](../api/queue.md#wait) |
| 120 | 0x78 | `SET_TRIG_CMD` | - |

## Extended I/O

| ID  | Hex  | Symbol | Magician method |
|-----|------|--------|-----------------|
| 130 | 0x82 | `GET_SET_IO_MULTIPLEXING` | [`set_multiplexing`](../api/io.md#set_multiplexing) |
| 131 | 0x83 | `GET_SET_IO_DO`           | [`set_do`](../api/io.md#set_do) |
| 132 | 0x84 | `GET_SET_IO_PWM`          | [`set_pwm`](../api/io.md#set_pwm) |
| 133 | 0x85 | `GET_IO_DI`               | [`get_di`](../api/io.md#get_di) |
| 134 | 0x86 | `GET_IO_ADC`              | [`get_adc`](../api/io.md#get_adc) |
| 135 | 0x87 | `SET_E_MOTOR`             | [`set_conveyor`](../api/accessories.md#set_converyor) |
| 136 | 0x88 | `SET_E_MOTOR_S`           | - |
| 137 | 0x89 | `GET_SET_COLOR_SENSOR`    | [`set_color_sensor`](../api/io.md#set_color_sensor), [`get_color_sensor`](../api/io.md#get_color_sensor) |
| 138 | 0x8A | `GET_SET_INFRARED_SENSOR` | [`set_infrared_sensor`](../api/io.md#set_infrared_sensor), [`get_infrared_sensor`](../api/io.md#get_infrared_sensor) |

## Calibration

| ID  | Hex  | Symbol | Magician method |
|-----|------|--------|-----------------|
| 140 | 0x8C | `GET_SET_ANGLE_SENSOR_STATIC_ERROR` | - |
| 141 | 0x8D | `GET_SET_ANGLE_SENSOR_COEF`         | - |
| 142 | 0x8E | `GET_SET_BASE_DECODER_STATIC_ERROR` | - |
| 143 | 0x8F | `GET_SET_LR_HAND_CALIBRATE_VALUE`   | - |

## WIFI

| ID  | Hex  | Symbol | Magician method |
|-----|------|--------|-----------------|
| 150 | 0x96 | `GET_SET_WIFI_CONFIG_MODE` | - |
| 151 | 0x97 | `GET_SET_WIFI_SSID`        | - |
| 152 | 0x98 | `GET_SET_WIFI_PASSWORD`    | - |
| 153 | 0x99 | `GET_SET_WIFI_IP_ADDRESS`  | - |
| 154 | 0x9A | `GET_SET_WIFI_NETMASK`     | - |
| 155 | 0x9B | `GET_SET_WIFI_GATEWAY`     | - |
| 156 | 0x9C | `GET_SET_WIFI_DNS`         | - |
| 157 | 0x9D | `GET_WIFI_CONNECT_STATUS`  | - |

## Lost-step detection

| ID  | Hex  | Symbol | Magician method |
|-----|------|--------|-----------------|
| 170 | 0xAA | `GET_SET_LOST_STEP_PARAMS` | [`set_lost_step_params`](../api/accessories.md#set_lost_step_params) |
| 171 | 0xAB | `SET_LOST_STEP_CMD`        | [`set_lost_step_cmd`](../api/accessories.md#set_lost_step_cmd) |

## Queued execution control

| ID  | Hex  | Symbol | Magician method |
|-----|------|--------|-----------------|
| 240 | 0xF0 | `SET_QUEUED_CMD_START_EXEC`     | [`start_queue`](../api/queue.md#start_queue), end of [`batch`](../api/queue.md#batch) |
| 241 | 0xF1 | `SET_QUEUED_CMD_STOP_EXEC`      | [`stop_queue`](../api/queue.md#stop_queue), start of [`batch`](../api/queue.md#batch) |
| 242 | 0xF2 | `SET_QUEUED_CMD_FORCE_STOP_EXEC`| [`force_stop_queue`](../api/queue.md#force_stop_queue) |
| 243 | 0xF3 | `SET_QUEUED_CMD_START_DOWNLOAD` | - |
| 244 | 0xF4 | `SET_QUEUED_CMD_STOP_DOWNLOAD`  | - |
| 245 | 0xF5 | `SET_QUEUED_CMD_CLEAR`          | [`clear_queue`](../api/queue.md#clear_queue), start of [`batch`](../api/queue.md#batch), [`connect`](../api/magician.md#connect) |
| 246 | 0xF6 | `GET_QUEUED_CMD_CURRENT_INDEX`  | [`queued_cmd_current_index`](../api/queue.md#queued_cmd_current_index), polled by [`wait_for`](../api/queue.md#wait_for) |
| 247 | 0xF7 | `GET_QUEUED_CMD_LEFT_SPACE`     | [`queued_cmd_left_space`](../api/queue.md#queued_cmd_left_space) |

## Commands without a method

Commands marked with a dash are sent with the [low-level methods](../api/low-level.md). Parameters are packed with the [packing functions](../api/low-level.md#parameter-packing).

```python
frame = bot.read_command(CommandID.GET_DEVICE_TIME)  # get, immediate
index = bot.queue_command(CommandID.SET_ARC_CMD, params_bytes)  # set, queued
```
