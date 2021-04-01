from spread_core.tools import settings
from spread_core.tools.settings import config

settings.DUMPED = False
PROJECT=config['PROJ']


HOSTnPORT = config['BUS_HOST_PORT']
TIMEOUT = config['BUS_TIMEOUT']
KILL_TIMEOUT = config['KILL_TIMEOUT']

ROJECT_ID = config['PROJECT_ID']
BROKER_HOST = config['BROKER_HOST']
BROKER_PORT = config['BROKER_PORT']
BROKER_USERNAME = config['BROKER_USERNAME']
BROKER_PWD = config['BROKER_PASSWORD']

OPCODEDISCONNECT = '0x0'
OPCODECONNECT = '0x1'
OPCODEERROR = '0x2'
OPCODEPINGREG = '0x3'
OPCODEPINGREQ = '0x4'
OPCODECANDATA = '0x7'


QUERY_ACTUAL_LEVEL='A0'
QUERY_GROU_07 = 'C0'
QUERY_GROU_811 = 'C1'
QUERY_IS_ON = '93'
QUERY_STATE ='90'
QUERY_FADE_TIME='A5'
DALI_GAP = 100

MIN_FADE_TIME = 0.3

MODBUS_DEV = config['MODBUS_DEV']
DALI_DEV = config['DALI_DEV']
DI_DEV = config['DI_DEV']
topic_dump = 'Tros3/{}'