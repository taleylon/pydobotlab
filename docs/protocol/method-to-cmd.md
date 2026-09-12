# Method ↔ command mapping

The reverse direction of the [Command ID table](command-ids.md) - every public `Magician` method, sorted alphabetically, with the protocol command ID it sends. Useful when you're staring at a wire trace and want to know "which Python call produced *this* frame?"

For each method: the `CommandID` it sends, the ctrl byte, and the param layout (in `struct`-ish notation; all multi-byte fields are little-endian).

| Method | Cmd ID | Ctrl | Param layout | Notes |
|--------|-------:|------|--------------|-------|
| [`batch()` *(enter)*](../api/queue.md#batch-context-manager) | 241 | `0x01` | – | Sends `SET_QUEUED_CMD_STOP_EXEC` on `__enter__`. |
| [`batch()` *(exit)*](../api/queue.md#batch-context-manager) | 240 | `0x01` | – | Sends `SET_QUEUED_CMD_START_EXEC` on `__exit__`. |
| [`clear_alarm`](../api/alarms.md#clear-alarm) | 20 | `0x01` | – | When `verify=True`, then re-reads cmd 20 read-side. |
| [`clear_queue`](../api/queue.md#clear_queue-none) | 245 | `0x01` | – | |
| [`cp`](../api/motion.md#cpx-y-z-velocity1000-mode1-int) | 91 | `0x03` | `u8 cpMode, f32 x, f32 y, f32 z, f32 velocity` | Continuous Path: consecutive `cp()` segments blend without per-segment decel. |
| [`connect`](../api/connection.md#connect-none) | 245→240 | `0x01` | – | Two frames: `CMD_CLEAR` then `CMD_START_EXEC` (skipped if `auto_start_queue=False`). |
| [`disconnect`](../api/connection.md#disconnect-none) | 241 | `0x01` | – | `STOP_EXEC` then close transport. |
| [`ensure_no_alarms`](../api/alarms.md#ensure_no_alarms-none) | 20 | `0x00` | – | Read alarm mask. |
| [`force_stop_queue`](../api/queue.md#force_stop_queue-none) | 242 | `0x01` | – | |
| [`get_adc`](../api/io.md#get_adcio-int) | 134 | `0x00` | `u8 port` | Returns `u16 value`. |
| [`get_alarms`](../api/alarms.md#get_alarms-alarmset) | 20 | `0x00` | – | Returns 16-byte mask. |
| [`get_arm_speed_ratio`](../api/speed.md#get_arm_speed_ratiomode-float) | 72 / 83 | `0x00` | – | 72 if `mode=0` (JOG), 83 if `mode=1` (PTP). |
| [`get_color_sensor`](../api/io.md#get_color_sensor-tupleint-int-int) | 137 | `0x00` | – | Returns `r, g, b` as 3 × u8. |
| [`get_device_name`](../api/extras.md#get_device_name-str) | 1 | `0x00` | – | |
| [`get_device_serial_number`](../api/extras.md#get_device_serial_number-str) | 0 | `0x00` | – | |
| [`get_device_version`](../api/extras.md#get_device_version-tupleint-int-int) | 2 | `0x00` | – | Returns `u8 major, u8 minor, u8 rev`. |
| [`get_di`](../api/io.md#get_diio-int) | 133 | `0x00` | `u8 port` | |
| [`get_infrared_sensor`](../api/io.md#get_infrared_sensorport-int) | 138 | `0x00` | `u8 port` | |
| [`get_jog_common_params`](../api/speed.md#get_jog_common_params-tuplefloat-float) | 72 | `0x00` | – | Returns `f32 vel, f32 acc`. |
| [`get_lost_step_result`](../api/extras.md#get_lost_step_result-liststr) | 20 | `0x00` | – | Re-uses `get_alarms`. |
| [`get_pose`](../api/motion.md#get_pose) | 10 | `0x00` | – | Returns 8 × f32: `x, y, z, r, j1..j4`. |
| [`get_posel`](../api/motion.md#get_posel-float) | 13 | `0x00` | – | Returns f32 mm. |
| `home` *(deprecated alias)* | 31 | `0x03` | `u32 mode=0` | See `set_home`. |
| [`jog`](../api/jog.md#jog-live-non-trajectory-motion) | 73 | `0x01` | `u8 isJoint, u8 cmd` | **Immediate**, not queued - see [Control byte](ctrl-byte.md). |
| [`jog_stop`](../api/jog.md#jog_stop-none) | 73 | `0x01` | `u8 isJoint, u8 0` | Sends JOGCmd.IDLE. |
| [`jump_params` *(getter)*](../api/speed.md#jump_params-property-tuplefloat-float) | 82 | `0x00` | – | |
| [`jump_params` *(setter)*](../api/speed.md#jump_params-property-tuplefloat-float) | 82 | `0x03` | `f32 jumpHeight, f32 zLimit` | API takes `(zlimit, height)`; wire order is swapped. |
| [`motion_params` *(getter)*](../api/speed.md#motion_params-property-tuplefloat-float) | 83 | `0x00` | – | |
| [`motion_params` *(setter)*](../api/speed.md#motion_params-property-tuplefloat-float) | 83 | `0x03` | `f32 vel, f32 acc` | |
| [`move_to`](../api/motion.md#move-to) | 84 | `0x03` | `u8 mode, f32 x, f32 y, f32 z, f32 r` | + waits on cmd 246. |
| [`ptp`](../api/motion.md#ptp-modes) | 84 | `0x03` | `u8 mode, f32 x, f32 y, f32 z, f32 r` | |
| [`queued_cmd_current_index`](../api/queue.md#queued_cmd_current_index-int) | 246 | `0x00` | – | Returns u64. |
| [`queued_cmd_left_space`](../api/queue.md#queued_cmd_left_space-int) | 247 | `0x00` | – | Returns u32. |
| [`set_color_sensor`](../api/io.md#set_color_sensorport-enable-version0-int) | 137 | `0x03` | `u8 enable, u8 port, u8 version` | |
| [`set_cp_params`](../api/speed.md#set_cp_paramsplan_acc-junction_vel-acc00-real_time_trackfalse-int) | 90 | `0x03` | `f32 planAcc, f32 junctionVel, f32 acc, u8 realTimeTrack` | Tune CP planner. |
| [`set_conveyor` / `set_converyor`](../api/extras.md#set_conveyorindex-enable-speed-int) | 135 | `0x03` | `u8 index, u8 enable, i32 speed` | |
| [`set_device_name`](../api/extras.md#set_device_namename-none) | 1 | `0x01` | ASCII bytes + `\0` | |
| [`set_device_withl`](../api/extras.md#set_device_withlenable-version0-int) | 3 | `0x03` | `u8 enable, u8 version` | |
| [`set_do`](../api/io.md#set_doio-level-int) | 131 | `0x03` | `u8 port, u8 level` | |
| [`set_endeffector_gripper`](../api/end-effectors.md#set_endeffector_gripperenable-on-int) | 63 | `0x03` | `u8 enableCtrl, u8 grip` | |
| [`set_endeffector_suctioncup`](../api/end-effectors.md#set_endeffector_suctioncupenable-on-int) | 62 | `0x03` | `u8 enableCtrl, u8 on` | |
| [`set_home`](../api/motion.md#set_home-waittrue-timeout600-raise_on_alarmtrue-int) | 31 | `0x03` | `u32 mode=0` | + waits on cmd 246. |
| [`set_infrared_sensor`](../api/io.md#set_infrared_sensorport-enable-version1-int) | 138 | `0x03` | `u8 enable, u8 port, u8 version` | |
| [`set_jog_common_params`](../api/speed.md#set_jog_common_paramsvel_ratio-acc_ratio-int) | 72 | `0x03` | `f32 vel, f32 acc` | |
| [`set_lost_step_cmd`](../api/extras.md#set_lost_step_cmd-int) | 171 | `0x03` | – | |
| [`set_lost_step_params`](../api/extras.md#set_lost_step_paramsvalue-int) | 170 | `0x03` | `f32 threshold` | |
| [`set_multiplexing`](../api/io.md#set_multiplexingio-multiplex-int) | 130 | `0x03` | `u8 port, u8 function` | |
| [`set_ptpl_params`](../api/speed.md#set_ptpl_paramsvel-accel-int) | 85 | `0x03` | `f32 vel, f32 acc` | |
| [`set_ptpwithl_cmd`](../api/motion.md#set_ptpwithl_cmdmode-x-y-z-r-l-int) | 86 | `0x03` | `u8 mode, f32 x, f32 y, f32 z, f32 r, f32 l` | |
| [`set_pwm`](../api/io.md#set_pwmio-freq-cycle-int) | 132 | `0x03` | `u8 port, f32 freq, f32 cycle` | |
| [`set_r`](../api/motion.md#set_rr-int) | 84 | `0x03` | `u8 mode, f32 x, f32 y, f32 z, f32 r` | Reads pose first, then sends `SET_PTP_CMD`. |
| [`start_pose_stream`](../api/pose-stream.md#start_pose_streamcallbacknone-hz500-queue) | 10 | `0x00` | – | Polls `GET_POSE` at `hz` Hz on a background thread. |
| [`start_queue`](../api/queue.md#start_queue-none) | 240 | `0x01` | – | |
| [`stop_pose_stream`](../api/pose-stream.md#stop_pose_stream-none) | – | – | – | Pure Python; no protocol I/O. |
| [`stop_queue`](../api/queue.md#stop_queue-none) | 241 | `0x01` | – | |
| [`wait`](../api/queue.md#waitsecond-int) | 110 | `0x03` | `u32 ms` | |
| [`wait_for`](../api/queue.md#wait_forindex-timeoutnone-poll002-raise_on_alarmtrue-none) | 246 + 20 | `0x00` | – | Polls cmd 246 (queue index) and cmd 20 read-side (alarms). |
| [`wait_idle`](../api/queue.md#wait_idle-timeoutnone-poll002-raise_on_alarmtrue-none) | 246 + 20 | `0x00` | – | As `wait_for`, target = last index this `Magician` queued. |

## Reading this table

* **Cmd ID** - decimal protocol ID. See the [Command ID table](command-ids.md) for the symbol name.
* **Ctrl** - `0x00` read-immediate, `0x01` write-immediate, `0x03` write-queued. (`0x02` read-queued isn't used in pydobotlab.)
* **Param layout** - what the host sends. Every multi-byte field is little-endian. `–` means no params.

When the response is a queued command, the response body is always a single `u64` queue index - that's the integer pydobotlab returns to your script.
