FIELD_ID = 'id'
FIELD_GET = 'get'
FIELD_SET = 'set'
FIELD_VARIANTS = 'variants'
FIELD_FORMAT = 'format'
FIELD_STATE = 'state'
FIELD_MULTIPLIER = 'multiplier'

DEVICE = 'Device'
MULTICAST = 'Multicast'
GROUP = 'Group'
PERSONAL_PROFILE = 'PersonalProfile'
CURRENT_PROFILE = 'CurrentProfile'
BRIGHTNESS_LEVEL = 'BrightnessLevel'

PROFILES = 'Profiles'
BINDING = 'Binding'
CONFIG = 'Config'
TIME = 'Time'
OPER_TIME = 'OperTime'
LATITUDE = 'Latitude'
LONGITUDE = 'Longitude'
ALTITUDE = 'Altitude'
TEMP = 'Temp'
TEMP_MIN = 'TempMin'
TEMP_MAX = 'TempMax'
ILLUMINATION = 'Illumination'
TILT = 'Tilt'
FLAGS = 'Flags'
EXTRA_FLAGS = 'ExtraFlags'
DALI_STATUS = 'DaliStatus'

SERIAL = 'Serial'
MODEL = 'Model'
FIRMWARE = 'Firmware'
ACTIVATION_STATUS = 'ActivationStatus'
USER_PASS = 'UserPass'
MC_ADDRESS_GROUP1 = 'McAddressGroup1'
DEV_EUI = 'DevEUI'
NETWORK_ID = 'NetworkId'
REGION = 'Region'
CLASS = 'Class'
NB_TRIALS = 'NBTrials'
TX_DATA_RATE = 'TXDataRate'
IS_PUBLIC_NETWORK = 'IsPublicNetwork'
ADDRESS_ENABLED = 'AddressEnabled'
GROUP1_ENABLED = 'Group1Enabled'
GROUP2_ENABLED = 'Group2Enabled'
GROUP3_ENABLED = 'Group3Enabled'
GROUP4_ENABLED = 'Group4Enabled'
REJOIN_INTERVAL = 'RejoinInterval'
TIME_SYNC_INTERVAL = 'TimeSyncInterval'
SEND_INTERVAL = 'SendInterval'
NW_CHECK_INTERVAL = 'NWCheckInterval'
NW_CHECK_ATTEMPTS = 'NWCheckAttempts'
CONFIRM_ENABLED = 'ConfirmEnabled'
ANGLE_THRESHOLD = 'AngleThreshold'
ACCEL_SENSITIVITY = 'AccelSensitivity'
DALI_SCAN_INTERVAL = 'DaliScanInterval'
ANSWER_RAND_INTERVAL = 'RandInterval'
ACTIVE_PROFILE = 'ActiveProfile'
SCAN = 'Scan'

CONFIGURATION = {
        SERIAL:                 dict(id=1),
        MODEL:                  dict(id=2),
        FIRMWARE:               dict(id=3),
        ACTIVATION_STATUS:      dict(id=4, state=bool),
        USER_PASS:              dict(id=6, state=str),
        MC_ADDRESS_GROUP1:      dict(id=7),
        DEV_EUI:                dict(id=8),
        NETWORK_ID:             dict(id=257, set=True),
        REGION:                 dict(id=258, set=True, variants=['AS923', 'AU915', 'CN470', 'CN779', 'EU433', 'EU868', 'KR920', 'IN865', 'US915', 'RU864']),
        CLASS:                  dict(id=259, set=True, variants=['CLASS_A', 'CLASS_B', 'CLASS_C']),
        NB_TRIALS:              dict(id=260, set=True),
        TX_DATA_RATE:           dict(id=261, set=True, format='DT{}'),
        IS_PUBLIC_NETWORK:      dict(id=262, set=True, state=bool),
        ADDRESS_ENABLED:        dict(id=263, set=True, state=bool),
        GROUP1_ENABLED:         dict(id=264, set=True, state=bool),
        GROUP2_ENABLED:         dict(id=281, set=True, state=bool),
        GROUP3_ENABLED:         dict(id=282, set=True, state=bool),
        GROUP4_ENABLED:         dict(id=283, set=True, state=bool),
        REJOIN_INTERVAL:        dict(id=265, set=True),
        TIME_SYNC_INTERVAL:     dict(id=266, set=True),
        SEND_INTERVAL:          dict(id=267, set=True),
        NW_CHECK_INTERVAL:      dict(id=268, set=True),
        NW_CHECK_ATTEMPTS:      dict(id=269, set=True),
        CONFIRM_ENABLED:        dict(id=270, set=True, state=bool),
        LATITUDE:               dict(id=271, set=True, multiplier=100000),
        LONGITUDE:              dict(id=272, set=True, multiplier=100000),
        ALTITUDE:               dict(id=273, set=True),
        ANGLE_THRESHOLD:        dict(id=274, set=True),
        ACCEL_SENSITIVITY:      dict(id=275, set=True, variants=['Off', 'Low', 'Middle', 'High']),
        DALI_SCAN_INTERVAL:     dict(id=276, set=True),
        ANSWER_RAND_INTERVAL:   dict(id=277, set=True),
        ACTIVE_PROFILE:    dict(id=278, set=True),
}
