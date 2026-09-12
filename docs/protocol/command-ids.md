# Command ID table

The full list of Dobot V1.1.5 command IDs that pydobotlab knows about. Source: `pydobotlab/commands.py` and the [official protocol PDF](https://www.alcom.no/wp-content/uploads/2019/11/Dobot-Communication-Protocol-V1.1.5-1.pdf).

For each entry: ID (decimal / hex), the symbolic name as it appears in `pydobotlab.commands.CommandID`, and the high-level `Magician` method that sends it (or "-" if pydobotlab doesn't wrap it yet, in which case you can still send it via `bot.write_command(CommandID.X, params)` / `bot.queue_command(CommandID.X, params)`).

## Device information

| ID  | Hex  | Symbol | Magician method |
|-----|------|--------|-----------------|
| 0   | 0x00 | `GET_DEVICE_SN`       | [`get_device_serial_number`](../api/extras.md#get_device_serial_number-str), [`is_dobot`](../api/discovery.md#is_dobotport-timeout04-bool), [`discover`](../api/discovery.md#discover-only_known_adaptersfalse-timeout04-skip-listdiscovereddobot) |
| 1   | 0x01 | `GET_SET_DEVICE_NAME` | [`get_device_name`](../api/extras.md#get_device_name-str), [`set_device_name`](../api/extras.md#set_device_namename-none) |
| 2   | 0x02 | `GET_DEVICE_VERSION`  | [`get_device_version`](../api/extras.md#get_device_version-tupleint-int-int) (used by the connection watchdog) |
| 3   | 0x03 | `GET_SET_DEVICE_WITH_L` | [`set_device_withl`](../api/extras.md#set_device_withlenable-version0-int) |
| 4   | 0x04 | `GET_DEVICE_TIME`     | - |
| 5   | 0x05 | `GET_DEVICE_ID`       | - |

## Real-time pose

| ID  | Hex  | Symbol | Magician method |
|-----|------|--------|-----------------|
| 10  | 0x0A | `GET_POSE`     | [`get_pose`](../api/motion.md#get_pose), [`start_pose_stream`](../api/pose-stream.md#start_pose_streamcallbacknone-hz500-queue) |
| 11  | 0x0B | `RESET_POSE`   | - |
| 12  | 0x0C | `GET_KINEMATICS` | - |
| 13  | 0x0D | `GET_POSE_L`   | [`get_posel`](../api/motion.md#get_posel-float) |

## Alarms

| ID  | Hex  | Symbol | Magician method |
|-----|------|--------|-----------------|
| 20  | 0x14 | `GET_ALARMS_STATE` *(read)* | [`get_alarms`](../api/alarms.md#get_alarms-alarmset), [`ensure_no_alarms`](../api/alarms.md#ensure_no_alarms-none), [`get_lost_step_result`](../api/extras.md#get_lost_step_result-liststr) |
| 20  | 0x14 | `CLEAR_ALL_ALARMS_STATE` *(write)* | [`clear_alarm`](../api/alarms.md#clear-alarm) |

> Same ID, different roles - selected by the [`rw` bit](ctrl-byte.md). See [Alarms](../api/alarms.md) for what the 16 mask bytes encode.

## Home

| ID  | Hex  | Symbol | Magician method |
|-----|------|--------|-----------------|
| 30  | 0x1E | `GET_SET_HOME_PARAMS` | - |
| 31  | 0x1F | `SET_HOME_CMD`        | [`set_home`](../api/motion.md#set_home-waittrue-timeout600-raise_on_alarmtrue-int) |
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
| 61  | 0x3D | `GET_SET_END_EFFECTOR_LASER`  | - |
| 62  | 0x3E | `GET_SET_END_EFFECTOR_SUCTION_CUP` | [`set_endeffector_suctioncup`](../api/end-effectors.md#set_endeffector_suctioncupenable-on-int) |
| 63  | 0x3F | `GET_SET_END_EFFECTOR_GRIPPER`     | [`set_endeffector_gripper`](../api/end-effectors.md#set_endeffector_gripperenable-on-int) |

## JOG

| ID  | Hex  | Symbol | Magician method |
|-----|------|--------|-----------------|
| 70  | 0x46 | `GET_SET_JOG_JOINT_PARAMS`      | - |
| 71  | 0x47 | `GET_SET_JOG_COORDINATE_PARAMS` | - |
| 72  | 0x48 | `GET_SET_JOG_COMMON_PARAMS`     | [`set_jog_common_params`](../api/speed.md#set_jog_common_paramsvel_ratio-acc_ratio-int), [`get_jog_common_params`](../api/speed.md#get_jog_common_params-tuplefloat-float) |
| 73  | 0x49 | `SET_JOG_CMD`                   | [`jog`](../api/jog.md#jog-live-non-trajectory-motion), [`jog_stop`](../api/jog.md#jog_stop-none) |
| 74  | 0x4A | `GET_SET_JOG_L_PARAMS`          | - |

## PTP

| ID  | Hex  | Symbol | Magician method |
|-----|------|--------|-----------------|
| 80  | 0x50 | `GET_SET_PTP_JOINT_PARAMS`      | - |
| 81  | 0x51 | `GET_SET_PTP_COORDINATE_PARAMS` | - |
| 82  | 0x52 | `GET_SET_PTP_JUMP_PARAMS`       | [`jump_params`](../api/speed.md#jump_params-property-tuplefloat-float) |
| 83  | 0x53 | `GET_SET_PTP_COMMON_PARAMS`     | [`motion_params`](../api/speed.md#motion_params-property-tuplefloat-float), [`get_arm_speed_ratio`](../api/speed.md#get_arm_speed_ratiomode-float) |
| 84  | 0x54 | `SET_PTP_CMD`                   | [`ptp`](../api/motion.md#ptp-modes), [`move_to`](../api/motion.md#move-to), [`set_r`](../api/motion.md#set_rr-int) |
| 85  | 0x55 | `GET_SET_PTP_L_PARAMS`          | [`set_ptpl_params`](../api/speed.md#set_ptpl_paramsvel-accel-int) |
| 86  | 0x56 | `SET_PTP_WITH_L_CMD`            | [`set_ptpwithl_cmd`](../api/motion.md#set_ptpwithl_cmdmode-x-y-z-r-l-int) |
| 87  | 0x57 | `GET_SET_PTP_JUMP_2_PARAMS`     | - |
| 88  | 0x58 | `SET_PTP_PO_CMD`                | - |
| 89  | 0x59 | `SET_PTP_PO_WITH_L_CMD`         | - |

## Continuous path (CP)

| ID  | Hex  | Symbol | Magician method |
|-----|------|--------|-----------------|
| 90  | 0x5A | `GET_SET_CP_PARAMS` | [`set_cp_params`](../api/speed.md#set_cp_paramsplan_acc-junction_vel-acc00-real_time_trackfalse-int) |
| 91  | 0x5B | `SET_CP_CMD`        | [`cp`](../api/motion.md#cpx-y-z-velocity1000-mode1-int) |
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
| 110 | 0x6E | `SET_WAIT_CMD` | [`wait`](../api/queue.md#waitsecond-int) |
| 120 | 0x78 | `SET_TRIG_CMD` | - |

## Extended I/O

| ID  | Hex  | Symbol | Magician method |
|-----|------|--------|-----------------|
| 130 | 0x82 | `GET_SET_IO_MULTIPLEXING` | [`set_multiplexing`](../api/io.md#set_multiplexingio-multiplex-int) |
| 131 | 0x83 | `GET_SET_IO_DO`           | [`set_do`](../api/io.md#set_doio-level-int) |
| 132 | 0x84 | `GET_SET_IO_PWM`          | [`set_pwm`](../api/io.md#set_pwmio-freq-cycle-int) |
| 133 | 0x85 | `GET_IO_DI`               | [`get_di`](../api/io.md#get_diio-int) |
| 134 | 0x86 | `GET_IO_ADC`              | [`get_adc`](../api/io.md#get_adcio-int) |
| 135 | 0x87 | `SET_E_MOTOR`             | [`set_conveyor`](../api/extras.md#set_conveyorindex-enable-speed-int) |
| 136 | 0x88 | `SET_E_MOTOR_S`           | - |
| 137 | 0x89 | `GET_SET_COLOR_SENSOR`    | [`set_color_sensor`](../api/io.md#set_color_sensorport-enable-version0-int), [`get_color_sensor`](../api/io.md#get_color_sensor-tupleint-int-int) |
| 138 | 0x8A | `GET_SET_INFRARED_SENSOR` | [`set_infrared_sensor`](../api/io.md#set_infrared_sensorport-enable-version1-int), [`get_infrared_sensor`](../api/io.md#get_infrared_sensorport-int) |

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
| 170 | 0xAA | `GET_SET_LOST_STEP_PARAMS` | [`set_lost_step_params`](../api/extras.md#set_lost_step_paramsvalue-int) |
| 171 | 0xAB | `SET_LOST_STEP_CMD`        | [`set_lost_step_cmd`](../api/extras.md#set_lost_step_cmd-int) |

## Queued execution control

| ID  | Hex  | Symbol | Magician method |
|-----|------|--------|-----------------|
| 240 | 0xF0 | `SET_QUEUED_CMD_START_EXEC`     | [`start_queue`](../api/queue.md#start_queue-none) |
| 241 | 0xF1 | `SET_QUEUED_CMD_STOP_EXEC`      | [`stop_queue`](../api/queue.md#stop_queue-none), end of [`batch`](../api/queue.md#batch-context-manager) |
| 242 | 0xF2 | `SET_QUEUED_CMD_FORCE_STOP_EXEC`| [`force_stop_queue`](../api/queue.md#force_stop_queue-none) |
| 243 | 0xF3 | `SET_QUEUED_CMD_START_DOWNLOAD` | - |
| 244 | 0xF4 | `SET_QUEUED_CMD_STOP_DOWNLOAD`  | - |
| 245 | 0xF5 | `SET_QUEUED_CMD_CLEAR`          | [`clear_queue`](../api/queue.md#clear_queue-none), `connect()` boot |
| 246 | 0xF6 | `GET_QUEUED_CMD_CURRENT_INDEX`  | [`queued_cmd_current_index`](../api/queue.md#queued_cmd_current_index-int), polled by [`wait_for`](../api/queue.md#wait_forindex-timeoutnone-poll002-raise_on_alarmtrue-none) |
| 247 | 0xF7 | `GET_QUEUED_CMD_LEFT_SPACE`     | [`queued_cmd_left_space`](../api/queue.md#queued_cmd_left_space-int) |

## Sending an unwrapped command yourself

If pydobotlab doesn't wrap the command you need (anything marked "-" in the tables above), you can still send it directly. The two private helpers on `Magician` are:

```python
# Read or write, immediate (no queue index in response):
frame = bot.send_command(CommandID.GET_DEVICE_VERSION, b"", write=False, queued=False)

# Write, queued (response is a u64 queue index):
idx = bot.queue_command(CommandID.SET_ARC_CMD, params_bytes)
```

Pack params using the helpers in `pydobotlab.protocol`: `pack_u8`, `pack_u16`, `pack_u32`, `pack_u64`, `pack_floats`. They all emit little-endian.

If you find yourself doing this, consider adding a wrapper to `device.py` and sending a PR.
