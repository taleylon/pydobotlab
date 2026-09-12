"""Command IDs for the Dobot Magician communication protocol (V1.1.5).

Every command the firmware understands has a single byte ID. The same ID is used
for both the "set" (write) and "get" (read) form of a command - the ``rw`` bit
of the control byte (see :mod:`pydobotlab.protocol`) selects which one.

Reference: https://www.alcom.no/wp-content/uploads/2019/11/Dobot-Communication-Protocol-V1.1.5-1.pdf
"""

from __future__ import annotations

from enum import IntEnum


class CommandID(IntEnum):
    # ---- Device information ------------------------------------------------
    GET_DEVICE_SN = 0
    GET_SET_DEVICE_NAME = 1
    GET_DEVICE_VERSION = 2
    GET_SET_DEVICE_WITH_L = 3
    GET_DEVICE_TIME = 4
    GET_DEVICE_ID = 5

    # ---- Real-time pose ----------------------------------------------------
    GET_POSE = 10  # x, y, z, r, j1..j4
    RESET_POSE = 11
    GET_KINEMATICS = 12
    GET_POSE_L = 13  # sliding rail position

    # ---- Alarms ------------------------------------------------------------
    GET_ALARMS_STATE = 20
    CLEAR_ALL_ALARMS_STATE = 20  # same id, write-side

    # ---- HOME --------------------------------------------------------------
    GET_SET_HOME_PARAMS = 30
    SET_HOME_CMD = 31
    SET_AUTO_LEVELING = 32

    # ---- Handhold teaching -------------------------------------------------
    GET_SET_HHT_TRIG_MODE = 40
    GET_SET_HHT_TRIG_OUTPUT_ENABLED = 41
    GET_HHT_TRIG_OUTPUT = 42

    # ---- Arm orientation ---------------------------------------------------
    GET_SET_ARM_ORIENTATION = 50

    # ---- End effector ------------------------------------------------------
    GET_SET_END_EFFECTOR_PARAMS = 60
    GET_SET_END_EFFECTOR_LASER = 61
    GET_SET_END_EFFECTOR_SUCTION_CUP = 62
    GET_SET_END_EFFECTOR_GRIPPER = 63

    # ---- JOG ---------------------------------------------------------------
    GET_SET_JOG_JOINT_PARAMS = 70
    GET_SET_JOG_COORDINATE_PARAMS = 71
    GET_SET_JOG_COMMON_PARAMS = 72
    SET_JOG_CMD = 73
    GET_SET_JOG_L_PARAMS = 74

    # ---- PTP ---------------------------------------------------------------
    GET_SET_PTP_JOINT_PARAMS = 80
    GET_SET_PTP_COORDINATE_PARAMS = 81
    GET_SET_PTP_JUMP_PARAMS = 82
    GET_SET_PTP_COMMON_PARAMS = 83
    SET_PTP_CMD = 84
    GET_SET_PTP_L_PARAMS = 85
    SET_PTP_WITH_L_CMD = 86
    GET_SET_PTP_JUMP_2_PARAMS = 87
    SET_PTP_PO_CMD = 88
    SET_PTP_PO_WITH_L_CMD = 89

    # ---- Continuous path (CP) ----------------------------------------------
    GET_SET_CP_PARAMS = 90
    SET_CP_CMD = 91
    SET_CP_LE_CMD = 92  # laser engraving

    # ---- ARC ---------------------------------------------------------------
    GET_SET_ARC_PARAMS = 100
    SET_ARC_CMD = 101
    SET_CIRCLE_CMD = 102
    GET_SET_ARC_COMMON_PARAMS = 103

    # ---- Wait / trig -------------------------------------------------------
    SET_WAIT_CMD = 110
    SET_TRIG_CMD = 120

    # ---- Extended I/O ------------------------------------------------------
    GET_SET_IO_MULTIPLEXING = 130
    GET_SET_IO_DO = 131
    GET_SET_IO_PWM = 132
    GET_IO_DI = 133
    GET_IO_ADC = 134
    SET_E_MOTOR = 135
    SET_E_MOTOR_S = 136
    GET_SET_COLOR_SENSOR = 137
    GET_SET_INFRARED_SENSOR = 138

    # ---- Calibration -------------------------------------------------------
    GET_SET_ANGLE_SENSOR_STATIC_ERROR = 140
    GET_SET_ANGLE_SENSOR_COEF = 141
    GET_SET_BASE_DECODER_STATIC_ERROR = 142
    GET_SET_LR_HAND_CALIBRATE_VALUE = 143

    # ---- WIFI --------------------------------------------------------------
    GET_SET_WIFI_CONFIG_MODE = 150
    GET_SET_WIFI_SSID = 151
    GET_SET_WIFI_PASSWORD = 152
    GET_SET_WIFI_IP_ADDRESS = 153
    GET_SET_WIFI_NETMASK = 154
    GET_SET_WIFI_GATEWAY = 155
    GET_SET_WIFI_DNS = 156
    GET_WIFI_CONNECT_STATUS = 157

    # ---- Lost-step detection -----------------------------------------------
    GET_SET_LOST_STEP_PARAMS = 170
    SET_LOST_STEP_CMD = 171

    # ---- Queued execution control ------------------------------------------
    SET_QUEUED_CMD_START_EXEC = 240
    SET_QUEUED_CMD_STOP_EXEC = 241
    SET_QUEUED_CMD_FORCE_STOP_EXEC = 242
    SET_QUEUED_CMD_START_DOWNLOAD = 243
    SET_QUEUED_CMD_STOP_DOWNLOAD = 244
    SET_QUEUED_CMD_CLEAR = 245
    GET_QUEUED_CMD_CURRENT_INDEX = 246
    GET_QUEUED_CMD_LEFT_SPACE = 247
