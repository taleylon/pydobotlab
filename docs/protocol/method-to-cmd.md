# Method ↔ command mapping

Each `Magician` method that sends a protocol command, in alphabetical order, with the command ID, control byte, and parameter layout it uses. Multi-byte fields are little-endian. The reverse mapping is the [Command ID table](command-ids.md).

| Method | Cmd ID | Ctrl | Param layout | Notes |
|--------|-------:|------|--------------|-------|
| [`batch()` *(enter)*](../api/queue.md#batch) | 241, 245 | `0x01` | – | `SET_QUEUED_CMD_STOP_EXEC`, then `SET_QUEUED_CMD_CLEAR`. Outermost block only. |
| [`batch()` *(exit)*](../api/queue.md#batch) | 240 | `0x01` | – | `SET_QUEUED_CMD_START_EXEC`, then waits as `wait_idle`. If the block raised: `SET_QUEUED_CMD_CLEAR` (245), then `SET_QUEUED_CMD_START_EXEC`. Outermost block only. |
| [`clear_alarm`](../api/alarms.md#clear_alarm) | 20 | `0x01` | – | Followed by a get of ID 20 after 0.2 s. |
| [`clear_queue`](../api/queue.md#clear_queue) | 245 | `0x01` | – | |
| [`connect`](../api/magician.md#connect) | 245, 240 | `0x01` | – | `SET_QUEUED_CMD_CLEAR`, then `SET_QUEUED_CMD_START_EXEC`. Omitted with `auto_start_queue=False`. |
| [`cp`](../api/motion.md#cp) | 91 | `0x03` | `u8 cpMode, f32 x, f32 y, f32 z, f32 velocity` | |
| [`disconnect`](../api/magician.md#disconnect) | 245, 240 | `0x01` | – | `SET_QUEUED_CMD_CLEAR`, then `SET_QUEUED_CMD_START_EXEC`. Omitted with `auto_start_queue=False`. |
| [`ensure_no_alarms`](../api/alarms.md#ensure_no_alarms) | 20 | `0x00` | – | Read alarm mask. |
| [`execute_command`](../api/low-level.md#execute_command) | any | `0x03` | caller's | + waits as `wait_for`, except inside `batch`. |
| [`force_stop_queue`](../api/queue.md#force_stop_queue) | 242 | `0x01` | – | |
| [`get_adc`](../api/io.md#get_adc) | 134 | `0x00` | `u8 port` | Returns `u16 value`. |
| [`get_alarms`](../api/alarms.md#get_alarms) | 20 | `0x00` | – | Returns 16-byte mask. |
| [`get_arm_speed_ratio`](../api/speed.md#get_arm_speed_ratio) | 72 / 83 | `0x00` | – | 72 if `mode=0` (JOG), 83 if `mode=1` (PTP). |
| [`get_color_sensor`](../api/io.md#get_color_sensor) | 137 | `0x00` | – | Returns `r, g, b` as 3 × u8. |
| [`get_device_name`](../api/magician.md#get_device_name) | 1 | `0x00` | – | |
| [`get_device_serial_number`](../api/magician.md#get_device_serial_number) | 0 | `0x00` | – | |
| [`get_device_version`](../api/magician.md#get_device_version) | 2 | `0x00` | – | Returns `u8 major, u8 minor, u8 rev`. |
| [`get_di`](../api/io.md#get_di) | 133 | `0x00` | `u8 port` | |
| [`get_infrared_sensor`](../api/io.md#get_infrared_sensor) | 138 | `0x00` | `u8 port` | |
| [`get_jog_common_params`](../api/speed.md#get_jog_common_params) | 72 | `0x00` | – | Returns `f32 vel, f32 acc`. |
| [`get_lost_step_result`](../api/accessories.md#get_lost_step_result) | 20 | `0x00` | – | Re-uses `get_alarms`. |
| [`get_pose`](../api/motion.md#get_pose) | 10 | `0x00` | – | Returns 8 × f32: `x, y, z, r, j1..j4`. |
| [`get_posel`](../api/accessories.md#get_posel) | 13 | `0x00` | – | Returns f32 mm. |
| `home` *(deprecated alias)* | 31 | `0x03` | `u32 mode=0` | Same as `set_home`. |
| [`jog`](../api/jog.md#jog) | 73 | `0x01` | `u8 isJoint, u8 cmd` | Immediate. See [Control byte](ctrl-byte.md). |
| [`jog_stop`](../api/jog.md#jog_stop) | 73 | `0x01` | `u8 isJoint, u8 cmd` | `cmd` is `JOGCmd.IDLE`. |
| [`jump_params` *(getter)*](../api/speed.md#jump_params) | 82 | `0x00` | – | |
| [`jump_params` *(setter)*](../api/speed.md#jump_params) | 82 | `0x03` | `f32 jumpHeight, f32 zLimit` | API takes `(zlimit, height)`; wire order is swapped. |
| [`motion_params` *(getter)*](../api/speed.md#motion_params) | 83 | `0x00` | – | |
| [`motion_params` *(setter)*](../api/speed.md#motion_params) | 83 | `0x03` | `f32 vel, f32 acc` | |
| [`move_to`](../api/motion.md#move_to) | 84 | `0x03` | `u8 mode, f32 x, f32 y, f32 z, f32 r` | + waits on cmd 246. |
| [`ptp`](../api/motion.md#ptp) | 84 | `0x03` | `u8 mode, f32 x, f32 y, f32 z, f32 r` | |
| [`queued_cmd_current_index`](../api/queue.md#queued_cmd_current_index) | 246 | `0x00` | – | Returns u64. |
| [`queued_cmd_left_space`](../api/queue.md#queued_cmd_left_space) | 247 | `0x00` | – | Returns u32. |
| [`set_color_sensor`](../api/io.md#set_color_sensor) | 137 | `0x03` | `u8 enable, u8 port, u8 version` | |
| [`set_conveyor` / `set_converyor`](../api/accessories.md#set_converyor) | 135 | `0x03` | `u8 index, u8 enable, i32 speed` | |
| [`set_cp_params`](../api/speed.md#set_cp_params) | 90 | `0x03` | `f32 planAcc, f32 junctionVel, f32 acc, u8 realTimeTrack` | |
| [`set_device_name`](../api/magician.md#set_device_name) | 1 | `0x01` | ASCII bytes + `\0` | |
| [`set_device_withl`](../api/accessories.md#set_device_withl) | 3 | `0x01` | `u8 enable, u8 version` | |
| [`set_do`](../api/io.md#set_do) | 131 | `0x03` | `u8 port, u8 level` | |
| [`set_endeffector_gripper`](../api/end-effectors.md#set_endeffector_gripper) | 63 | `0x03` | `u8 enableCtrl, u8 grip` | |
| [`set_endeffector_laser`](../api/end-effectors.md#set_endeffector_laser) | 61 | `0x03` | `u8 enableCtrl, u8 on` | |
| [`set_endeffector_suctioncup`](../api/end-effectors.md#set_endeffector_suctioncup) | 62 | `0x03` | `u8 enableCtrl, u8 on` | |
| [`set_home`](../api/motion.md#set_home) | 31 | `0x03` | `u32 mode=0` | |
| [`set_infrared_sensor`](../api/io.md#set_infrared_sensor) | 138 | `0x03` | `u8 enable, u8 port, u8 version` | |
| [`set_jog_common_params`](../api/speed.md#set_jog_common_params) | 72 | `0x03` | `f32 vel, f32 acc` | |
| [`set_lost_step_cmd`](../api/accessories.md#set_lost_step_cmd) | 171 | `0x03` | – | |
| [`set_lost_step_params`](../api/accessories.md#set_lost_step_params) | 170 | `0x01` | `f32 threshold` | |
| [`set_multiplexing`](../api/io.md#set_multiplexing) | 130 | `0x03` | `u8 port, u8 function` | |
| [`set_ptpl_params`](../api/accessories.md#set_ptpl_params) | 85 | `0x03` | `f32 vel, f32 acc` | |
| [`set_ptpwithl_cmd`](../api/accessories.md#set_ptpwithl_cmd) | 86 | `0x03` | `u8 mode, f32 x, f32 y, f32 z, f32 r, f32 l` | |
| [`set_pwm`](../api/io.md#set_pwm) | 132 | `0x03` | `u8 port, f32 freq, f32 cycle` | |
| [`set_r`](../api/motion.md#set_r) | 84 | `0x03` | `u8 mode, f32 x, f32 y, f32 z, f32 r` | Reads pose first, then sends `SET_PTP_CMD`. |
| [`start_pose_stream`](../api/pose-stream.md#start_pose_stream) | 10 | `0x00` | – | Repeated `GET_POSE`. |
| [`start_queue`](../api/queue.md#start_queue) | 240 | `0x01` | – | |
| [`stop_pose_stream`](../api/pose-stream.md#stop_pose_stream) | – | – | – | Sends no command. |
| [`stop_queue`](../api/queue.md#stop_queue) | 241 | `0x01` | – | |
| [`wait`](../api/queue.md#wait) | 110 | `0x03` | `u32 ms` | |
| [`wait_for`](../api/queue.md#wait_for) | 246, 20 | `0x00` | – | Repeated gets of the queue index (246) and, with `raise_on_alarm`, the alarms (20). On an alarm, `SET_QUEUED_CMD_CLEAR` (245). |
| [`wait_idle`](../api/queue.md#wait_idle) | 246, 20 | `0x00` | – | As `wait_for`, for the last index queued by this instance. |

## Columns

- **Cmd ID**: decimal ID. The `CommandID` member names are in the [Command ID table](command-ids.md).
- **Ctrl**: `0x00` get, immediate. `0x01` set, immediate. `0x03` set, queued. See [Control byte](ctrl-byte.md).
- **Param layout**: parameters sent by the host. A dash means none.

The response to a queued set command is a `u64` queue index. The DobotLab functions with control byte `0x03` then wait as [`wait_for`](../api/queue.md#wait_for) does, except inside [`batch`](../api/queue.md#batch).
