import json
import socket
import threading
import time
import random
import json
import paho.mqtt.client
from threading import Timer
import bitstring
import copy
from bitstring import BitArray
import array

from spread_core.mqtt.variables import VariableJocket, VariableTRS3, VariableReader
from spread_core.tools import settings
from spread_core.tools.service_launcher import Launcher
from spread_core.tools.settings import config, logging
from spread_core.mqtt.variables import VariableJocket

settings.DUMPED = False
PROJECT=config['PROJ']
BUS_ID=config['BUS_ID']

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

MIN_FADE_TIME = 0.5

CLASS_TABLE = {
    'Air':1090000,
    'VentilationUnit': 1090100,
        'VentilationUnit_On': 1090101,
        'VentilationUnit_TargetTemperature': 1090102,
        'VentilationUnit_OperationMode': 1090110,
        'VentilationUnit_NoInputVoltage': 1090131,
    'ElectricAirHeater':1090200,
        'ElectricAirHeater_On': 1090201,
        'ElectricAirHeater_PowerLevel': 1090203,
        'ElectricAirHeater_Overheat': 1090233,
    'WaterAirHeater': 1090300,
        'WaterAirHeater_FreezingThreat': 1090334,
    'WaterAirCooler': 1090400,
        'WaterAirCooler_FreezingThreat': 1090434,
    'InflowDuctFan': 1090500,
        'InflowDuctFan_On': 1090501,
        'InflowDuctFan_RunningTime': 1090511,
        'InflowDuctFan_Overheat': 1090533,
        'InflowDuctFan_NoPressureDrop': 1090532,
    'OutflowDuctFan': 1090600,
        'OutflowDuctFan_On': 1090601,
        'OutflowDuctFan_RunningTime': 1090611,
        'OutflowDuctFan_Overheat': 1090633,
        'OutflowDuctFan_NoPressureDrop': 1090632,
    'InflowAirValve':  1090700,
        'InflowAirValve_Open': 1090701,
    'OutflowAirValve':  1090800,
        'OutflowAirValve_Open': 1090801,
    'InflowAirFilter':  1090900,
        'InflowAirFilter_Dirty':  1090935,
    'OutflowAirFilter':  1091000,
        'OutflowAirFilter_Dirty': 1091035,
    'HeaterWaterValve': 1091100,
        'HeaterWaterValve_OpenLevel': 1091101,
    'CoolerWaterValve': 1091200,
        'CoolerWaterValve_OpenLevel': 1091201,
    'HeaterWaterPump':  1091300,
        'HeaterWaterPump_On': 1091301,
        'HeaterWaterPump_RunningTime': 1091311,
        'HeaterWaterPump_Overheat': 1091333,
    'CoolerWaterPump': 1091400,
        'CoolerWaterPump_On': 1091401,
        'CoolerWaterPump_RunningTime': 1091411,
        'CoolerWaterPump_Overheat':  1091433,
    'DuctTemperatureSensor': 1091500,
        'DuctTemperatureSensor_Temperature': 1091512,
    'ImmersionTemperatureSensor': 1091600,
        'ImmersionTemperatureSensor_Temperature': 1091612,
}

MODBUS_DEV = config['MODBUS_DEV']
DALI_DEV = config['DALI_DEV']

# topic_dump = 'Tros3/State/{}/{}/{}'
# topic_send = 'ModBus/from_Client/{}'
topic_send =config['TOPIC_SEND']
topic_dump = config['TOPIC_DUMP']

is_lock=False

current_milli_time = lambda: int(round(time.time() * 1000))

def hex_to_bool(x):
    if x=='FE'or x=='fe' or x=='FF' or 'ff':
        return True
    elif x=='00':
        return False

def isONID(x):
    if x == 'SwitchingLight':
        return 2
    elif x == 'DimmingLight':
        return 2
    elif x == 'LeakageSensor':
        return 0
    else:
        return 'On'

def make_two_bit(x):
    bytes_list =list('00')
    list_x = list(x)
    i=-1
    while abs(i) <= len(x):
        bytes_list[i]=list_x[i]
        i=i-1
    return ''.join(bytes_list)

def make_bytes(x):
    bytes_list =list('0000')
    list_x = list(x)
    i=-1
    while abs(i) <= len(x):
        bytes_list[i]=list_x[i]
        i=i-1
    return ''.join(bytes_list)

def CanId(addrFrom, addrTo):
    addr_from_ = bitstring.BitArray(hex(addrFrom))
    addr_to_ = bitstring.BitArray(hex(addrTo))
    if addr_from_.length < 5:
        addr_from = bitstring.BitArray(5-addr_from_.length)
        addr_from.append(addr_from_)
    elif addr_from_.length >= 5:
        addr_from = addr_from_[(addr_from_.length-5):]

    if addr_to_.length < 5:
        addr_to = bitstring.BitArray(5 - addr_to_.length)
        addr_to.append(addr_to_)
    elif addr_to_.length >= 5:
        addr_to = addr_to_[(addr_to_.length - 5):]

    addr_from.append(addr_to)
    can_id = bitstring.BitArray(12 - addr_from.length)
    can_id.append(addr_from)

    return make_bytes(can_id.hex)

def ShortDaliAddtessComm(devAddr, data, cfl=0):

    devaddr = bitstring.BitArray(hex(devAddr))
    daddr = bitstring.BitArray(6 - devaddr.length)
    daddr.append(devaddr)
    addrbyte = bitstring.BitArray(bin(0))
    addrbyte.append(daddr)
    addrbyte.append(bitstring.BitArray(bin(cfl)))
    if isinstance(data, int):
        dd = addrbyte.hex + make_two_bit(hex(data).split('x')[1])
    elif isinstance(data, str):
        dd_=data.split('x')
        if len(dd_)>1:
            dd = addrbyte.hex + make_two_bit(dd_[1])
        else:
            dd = addrbyte.hex + make_two_bit(dd_[0])
    return dd

def GroupDaliAddtessComm(groupAddr, data, cfl=0):

    devaddr = bitstring.BitArray(hex(groupAddr))
    daddr = bitstring.BitArray(6 - devaddr.length)
    daddr.append(devaddr)
    addrbyte = bitstring.BitArray(bin(1))
    addrbyte.append(daddr)
    addrbyte.append(bitstring.BitArray(bin(cfl)))
    if isinstance(data, int):
        dd = addrbyte.hex + make_two_bit(hex(data).split('x')[1])
    elif isinstance(data, str):
        dd_=data.split('x')
        if len(dd_)>1:
            dd = addrbyte.hex + make_two_bit(dd_[1])
        else:
            dd = addrbyte.hex + make_two_bit(dd_[0])
    return dd

def Byte0(clss, cmd=False):

    byte0 = bitstring.BitArray(1)
    byte0[0]=cmd

    echo = bitstring.BitArray(1)
    reserve = bitstring.BitArray(1)
    cls_ = bitstring.BitArray(hex(clss))
    if cls_.length < 5:
        cls = bitstring.BitArray(5 - cls_.length)
        cls.append(cls_)
    elif cls_.length >= 5:
        cls = cls_[(cls_.length - 5):]
    byte0.append(echo)
    byte0.append(reserve)
    byte0.append(cls)

    return byte0

def Byte1(waitAns=False, st=False):
    byte1_=bitstring.BitArray(8)
    if waitAns:
        byte1_[7]=waitAns
    if st:
        byte1_[5]=st
    byte1 = byte1_.hex

    return byte1

def ByteStrToStr(out):
    out_str = '{}'.format(''.join(hex(b)[2:].rjust(2, '0').upper() for b in out))
    return out_str

class ModBusProvider:
    def __init__(self, rpgClient, mqtt, *args):
        self._socket = rpgClient
        self.dev = args[0]
        self._mqtt = mqtt
        self._callMTime = 0
        self.state = args[0]['dev']['value']
        self.stateInt = 0
        self.lastState = None
        self.lastStateInt = 0
        self.isValid = True
        self.oneByteAnswer = None
        self.twoByteAnswer = None
        self.BytesAnswer = None
        self.typeOfQuery = None # 0 - no answer, 1 - need answer
        # self.bus = args[0]['dev']['bus']
        # self.channel = args[0]['dev']['channel']
        self.time_gap = args[0]['t_gap']
        self._call = None
        self.answerIs = None
        self.maddr = args[0]['dev']['maddr']
        self.reg = args[0]['attrib']['reg']
        self.topType = args[0]['topic_type'][0]
        self.tt = args[0]['topic_type'][1]
        # self._stateTopicLevel = '{}/State/{}/Equipment/{}/{}/0'.format(self.topType, PROJECT, args[0]['dev']['type'], args[0]['dev']['id'])
        # self._stateTopicIsOn = '{}/State/{}/Equipment/{}/{}/{}'.format(self.topType, PROJECT, args[0]['dev']['type'], args[0]['dev']['id'], isONID(args[0]['dev']['type']))
        self._stateTopicLevel = '{}/State/{}/Equipment/{}/{}/0'.format(self.topType, PROJECT, args[0]['dev']['type'], args[0]['dev']['id'][0])
        self._stateTopicIsOn = '{}/State/{}/Equipment/{}/{}/{}'.format(self.topType, PROJECT, args[0]['dev']['type'], args[0]['dev']['id'][0], args[0]['topic_type'][1])
        self.answer = None


    def setValue(self, val):
        self.isValid=True
        b_=''
        self.state = val
        for b in val:
            b_=b_+hex(b).split('x')[1]
        self.stateInt = int(b_, 16)
        if self.lastState is None:
            self.lastState = val
            self.lastStateInt = self.stateInt
            self.dumpMqtt()

    @property
    def getCallTime(self):
        return self._callMTime


    def askLevel(self):
        pass


    def work(self):
        if abs(self.stateInt-self.lastStateInt)/self.stateInt*100. >= self.dev['pres']:
            self.lastState = self.state
            self.lastStateInt = self.stateInt
            self.dumpMqtt()

    def queryModBusState(self):
        #    чтение регистров

        transaction_id = hex(random.getrandbits(10)).split('x')[1]
        transaction_id = make_bytes(transaction_id)

        data_id = make_two_bit(hex(self.dev['dev']['maddr']).split('x')[1])

        data_command = make_two_bit(self.dev['attrib']['command_ask'].split('x')[1])
        data_reg = make_bytes(hex(self.dev['attrib']['reg']).split('x')[1])
        data_nreg = make_bytes(hex(self.dev['attrib']['nreg']).split('x')[1])

        data = data_id + data_command + data_reg + data_nreg

        mbCommand = data

        pLen = bytearray(4)
        pLen[3] = int(len(mbCommand) / 2)

        pL = make_two_bit(hex(pLen[0]).split('x')[1]) + \
             make_two_bit(hex(pLen[1]).split('x')[1]) + make_two_bit(hex(pLen[2]).split('x')[1]) + \
             make_two_bit(hex(pLen[3]).split('x')[1]) + mbCommand
        pL = transaction_id + pL
        size = len(pL)
        dd = bytes.fromhex(pL)

        out = self._socket.send_message(dd, size)
        self.answerIs = out
        if out is not None:
            result = ByteStrToStr(out)
            if result[:4].lower() == transaction_id:
                out_ = out[2:]
                res, rest = self.parceModBusData(out_)
                if res['payload']['error'] == bytearray():
                    self.BytesAnswer = res['payload']['data']
                    self.isValid = True
                    if res['payload']['nbyte'][0] == 2 or res['payload']['nbyte'][0] == 1:
                        # только для опроса одного регистра !!!!!!!!!!!!!
                        res['payload']['data'].reverse()
                        intRes = bitstring.BitArray(res['payload']['data']).int
                        res['intRes'] = intRes
                else:
                    self.isValid = False
            else:

                res = None
        else:
            res = None
            self.isValid=False

        return res


    def callModBus(self, data = None, part=False):
        # запись в регистры

        self._call = data

        transaction_id = hex(random.getrandbits(10)).split('x')[1]
        transaction_id = make_bytes(transaction_id)

        data_id = make_two_bit(hex(self.dev['dev']['maddr']).split('x')[1])
        data_command = make_two_bit(self.dev['attrib']['command'].split('x')[1])
        data_reg = make_bytes(hex(self.dev['attrib']['reg']).split('x')[1])
        data_nreg = make_bytes(hex(self.dev['attrib']['nreg']).split('x')[1])
        if self.dev['attrib']['command'] == '0x10':
            if data is None:
                data = data_id + data_command + data_reg + data_nreg
            else:
                data = data_id + data_command + data_reg + data_nreg + make_bytes(hex(data).split('x')[1])
        elif self.dev['attrib']['command'] == '0x03' or self.dev['attrib']['command'] == '0x06':
            if data is None:
                data = data_id + data_command + data_reg
            else:
                data_ = make_bytes(hex(data).split('x')[1])
                data = data_id + data_command + data_reg + data_[2:] + data_[:2]

        mbCommand = data

        pLen = bytearray(4)
        pLen[3] = int(len(mbCommand) / 2)
        # pL = opCode + make_two_bit(hex(pLen[0]).split('x')[1]) + \
        #      make_two_bit(hex(pLen[1]).split('x')[1]) + make_two_bit(hex(pLen[2]).split('x')[1]) + \
        #      mbCommand
        pL = make_two_bit(hex(pLen[0]).split('x')[1]) + \
             make_two_bit(hex(pLen[1]).split('x')[1])  + make_two_bit(hex(pLen[2]).split('x')[1])+ \
             make_two_bit(hex(pLen[3]).split('x')[1]) + mbCommand
        pL = transaction_id + pL
        size = len(pL)
        dd = bytes.fromhex(pL)

        out = self._socket.send_message(dd, size)
        self.answerIs=out
        self._callMTime = current_milli_time()

    def dumpMqtt(self, data=None, fl = 0, classId = None):
        # if data == None:
        #     data = self.stateInt
        if data == None and self.state is not None:
            data = self.state
        else:
            self.state = data
        # out = VariableTRS3(None, self.dev['dev']['id'], 0, data, invalid=(not self.isValid))
        if self.topType == 'Tros3':
            out_ = VariableTRS3(id=self.dev['dev']['id'][0], cl=fl, val=data)
            out = out_.pack()
        elif self.topType == 'Jocket':
            if classId is None:
                classId = CLASS_TABLE[self.dev['dev']['type']+'_'+self.tt]
            out_ = VariableJocket.create_data(id=self.dev['dev']['id'][0], cl=classId, action='state' ,val=data)
            out  = out_.pack()
        if fl == 0:
            clientTopic = self._stateTopicLevel
        elif fl == 2:
            clientTopic = self._stateTopicIsOn
        # clientTopic = self._stateTopicLevel

        self._mqtt.publish(topic=clientTopic, payload=out, qos=0, retain=True)

    def parceModBusData(self, message):
            dataAr = list(bytearray(0))
            for b in message:
                dataAr.append(b)
            data = {

                'protocol': bytearray(2),
                'len': bytearray(2),
                'payload': {
                    'id': bytearray(1),
                    'comres': bytearray(1),
                    'nbyte': bytearray(),
                    'error': bytearray(),
                    'data': bytearray(),
                }
            }
            for i in range(2):
                data['protocol'][i] = dataAr.pop(0)

            for i in range(2):
                data['len'][i] = dataAr.pop(0)
            length = bitstring.BitArray(data['len']).int

            data['payload']['id'][0] = dataAr.pop(0)

            data['payload']['comres'][0] = dataAr.pop(0)
            comres = bitstring.BitArray(hex(data['payload']['comres'][0]))
            if comres[0] :
                for i in range(length - 2):
                    data['payload']['error'].append(dataAr.pop(0))
            else:
                data['payload']['nbyte'].append(dataAr.pop(0))
                for i in range(length - 3):
                    data['payload']['data'].append(dataAr.pop(0))

            return data, dataAr

class DaliProvider:
    def __init__(self, rpgClient, mqtt, *args):
        self._socket = rpgClient
        self.dev = args[0]
        self._mqtt = mqtt
        self._callDTime = 0
        self.state = None
        self.lastLevel = 0
        self.fadeTime = 0.
        self.timeOfChange = time.time()
        self.isValid = None
        self.oneByteAnswer = None
        self.twoByteAnswer = None
        self.typeOfQuery = None # 0 - no answer, 1 - need answer
        self.group1 = bitstring.BitArray(8)
        self.group2 = bitstring.BitArray(8)
        self.groupList=list()
        self._call = None
        self.answerIs = False
        self.dadr = args[0]['dadr']
        self._stateTopicLevel = 'Tros3/State/{}/Equipment/{}/{}/4'.format(PROJECT, args[0]['type'], args[0]['id'])
        self._stateTopicIsOn = 'Tros3/State/{}/Equipment/{}/{}/{}'.format(PROJECT, args[0]['type'], args[0]['id'], isONID(args[0]['type']))
        self.answer = None


    def setValue(self, val):

        self.state = val

    @property
    def getCallTime(self):
        return self._callDTime

    def getAnswer(self, data):
        print('dali answer is {}'.format(data))
        self.answerIs = True


    def askLevel(self):
        pass

    def askGroup(self):
        pass

    def setLevel(self, data):
        # set level on dali device
        self._call = data
        mbCommand = 'E203010001' + data
        opCode = '07'
        pLen = bytearray(3)
        pLen[0] = int(len(mbCommand) / 2)
        pL = opCode + make_two_bit(hex(pLen[0]).split('x')[1]) + \
             make_two_bit(hex(pLen[1]).split('x')[1]) + make_two_bit(hex(pLen[2]).split('x')[1]) + \
             mbCommand
        size = len(pL)
        data = bytes.fromhex(pL)
        self._callDTime = current_milli_time()
        out = self._socket.send_message(data, size)
        self.answerIs=False
        return self._callDTime

    def callDali(self, data, resp=False):
        self._call = data

        addr_from = bitstring.BitArray(hex(31))[3:]
        addr_to_ = bitstring.BitArray(hex(self.dev['bus']))
        addr_to = bitstring.BitArray(5-addr_to_.length)
        addr_to.append(addr_to_)
        addr_from.append(addr_to)
        can_id = bitstring.BitArray(12-addr_from.length)
        can_id.append(addr_from)
        canId = make_bytes(can_id.hex)


        byte0 = bitstring.BitArray(1)
        echo = bitstring.BitArray(1)
        reserve = bitstring.BitArray(1)
        cls = bitstring.BitArray(5)
        cls[4]=True
        byte0.append(echo)
        byte0.append(reserve)
        byte0.append(cls)

        byte1 = bitstring.BitArray(8)
        byte1[5]=resp

        byte2=bitstring.BitArray(8)
        byte2[7-self.dev['channel']]=True

        dCommand = canId[2:] + canId[:2] + byte0.hex + byte1.hex + byte2.hex
        # mbCommand = 'E203010001' + data
        mbCommand = dCommand + data
        opCode = '07'
        pLen = bytearray(3)
        pLen[0] = int(len(mbCommand) / 2)
        pL = opCode + make_two_bit(hex(pLen[0]).split('x')[1]) + \
             make_two_bit(hex(pLen[1]).split('x')[1]) + make_two_bit(hex(pLen[2]).split('x')[1]) + \
             mbCommand
        size = len(pL)
        dd = bytes.fromhex(pL)
        self._callDTime = current_milli_time()
        out = self._socket.send_message(dd, size)
        self.answerIs=False
        return self._callDTime

    def dumpMqtt(self, data=None, fl=None, comm = 0, flInvalid = False):
        if data == None and self.state is not None:
            data_ = self.state
            data = data_.uint

        # out = VariableTRS3(None, self.dev['id'], 0, data, invalid=(not self.isValid))
        # if self.isValid == False:
        #     data = None
        out = VariableTRS3(None, self.dev['id'], comm, data)
        if fl == None:
            clientTopic = self._stateTopicLevel
        elif fl == 1:
            clientTopic = self._stateTopicIsOn
        self._mqtt.publish(topic=clientTopic, payload=out.pack(), qos=0, retain=True)



class RGPTcpSocket:

    def __init__(self, host, port):

        self._killer = None
        self._port=port
        self._host=host

        self.sock=None
        #self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #self.sock.settimeout(TIMEOUT)
        #self._commands=commands



    def create(self):
        logging.debug('Create socket')
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(TIMEOUT)
        while True:
            try:

                self.sock.connect((self._host, self._port))
            except ConnectionRefusedError as ex:
                logging.exception(ex)
                time.sleep(3)
            else:
                break

    def start_timer(self):
        if KILL_TIMEOUT > 0:
            self._killer = Timer(KILL_TIMEOUT, self.kill)
            self._killer.start()

    def stop_timer(self):
        if self._killer:
            self._killer.cancel()
            self._killer = None

    def kill(self):
        if isinstance(self.sock, socket.socket):
            logging.debug('Kill socket')
            self.sock.close()
            self.sock = None

    def send_message(self, data, r_size):
        self.stop_timer()
        if self.sock is None:
            self.create()
        self.sock.send(data)
        print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
        logging.debug('[->  ]: {}'.format(' '.join(hex(b)[2:].rjust(2, '0').upper() for b in data)))
        print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
        try:
            out = self.sock.recv(1024)
        except BaseException as ex:
            logging.exception(ex)
            return None
        logging.debug('[  <-]: {}'.format(' '.join(hex(b)[2:].rjust(2, '0').upper() for b in out)))
        # out_str = '{}'.format(''.join(hex(b)[2:].rjust(2, '0').upper() for b in out))
        out_str = out
        return out_str




    def recive_data(self):
        self.stop_timer()
        if self.sock is None:
            self.create()
        try:
            out = self.sock.recv(64)
        except  BaseException as ex:
            # logging.exception(ex)
            return None
        else:
            print('<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<')
            logging.debug('[  <-]: {}'.format(' '.join(hex(b)[2:].rjust(2, '0').upper() for b in out)))
            print('<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<')
            # out_str = '{}'.format(''.join(hex(b)[2:].rjust(2, '0').upper() for b in out))
            return out

    # def commands(self):
    #     return self._commands


class RGPTCPAdapterLauncher:
    _dumped = False
    _command_event = threading.Event()

    def __init__(self):
        self._time = current_milli_time()
        self.mqttc = paho.mqtt.client.Client()
        self.mqttc.username_pw_set(BROKER_USERNAME, BROKER_PWD)
        self.mqttc.on_connect = self.on_connect
        self.mqttc.on_disconnect = self.on_disconnect
        self.mqttc.on_subscribe = self.on_subscribe
        self.mqttc.on_message = self.on_message
        self.mqttc.connect(BROKER_HOST, BROKER_PORT)
        self._manager = self
        self._stopped = False
        self.sock= RGPTcpSocket(HOSTnPORT[0][0], HOSTnPORT[0][1])
        self._start_time = time.time()
        self.callDaliTime = current_milli_time()
        self.callModBusTime = current_milli_time()
        self.daliProviders = []
        self.modbusProviders = []
        self.daliGroup = [[] for i in range(0, 16)]
        self.daliAnswer=None   # 0 - no answer,
                                # 1 - ok,
        #                        -1 - 8 bit answer - no needed answer,
        #                        -2 - 8 bit answer - no echo from dali
        #                        -3 - error on dali line
        #                        -4 - time gap is exceeded
        self.isDaliQueried = False
        self.modbusAnswer = False
        self.callDaliProvider = None
        self.beginTime = None
        self.modBusEv = threading.Event()
        self.startEvent = threading.Event()



        for prov in DALI_DEV:
            daliDev = DaliProvider(self.sock, self.mqttc, prov)
            self.daliProviders.append(daliDev)

        for prov in MODBUS_DEV:
            modbusDev = ModBusProvider(self.sock, self.mqttc, prov)
            self.modbusProviders.append(modbusDev)

        # for prov in self.daliProviders:
        #     for index, val in prov.dev['FunctionUnitIndex'].items():
        #         topic = 'Jocket/Command/{}/#'.format(PROJECT)
        #         self.mqttc.subscribe(topic)
        #         logging.debug('Subscribed to {}'.format(topic))
        # topic = 'Tros3/Command/{}/#'.format(PROJECT)
        topic = [('Tros3/Command/{}/#'.format(PROJECT), 0), ('Jocket/Command/{}/#'.format(PROJECT), 0)]
        self.mqttc.subscribe(topic)
        logging.debug('Subscribed to {}'.format(topic))


    def start(self):
        self._command_event.set()
        # self.connect_rpg()
        # self.rpg_listen_fun()

        # пингование не нужно
        # listen = threading.Thread(target=self.listen_rpg, args=(self.startEvent,))
        # слушанье шлюза не нужно
        # listen1 = threading.Thread(target=self.listen_rpg1, args=(self.startEvent,))

        listen2 = threading.Thread(target=self.modbusQuery, args=(self.modBusEv,))



        # listen.start()

        # listen1.start()

        self.start_dali()

        listen2.start()
        self.modBusEv.set()
        self.startEvent.set()

        self.mqttc.loop_forever()

        # self.test_dali_num()

    def on_connect(self, mqttc, userdata, flags, rc):
        if rc==0:
            print("connected OK Returned code=",rc)
        else:
            print("Bad connection Returned code=",rc)

    def on_disconnect(self, mqttc, userdata, rc):
        if rc != 0:
            print("Unexpected MQTT disconnection. Will auto-reconnect")
            self.mqttc.reconnect()

    def on_subscribe(self, mqttc, userdata, mid, granted_qos):
        print("Subscribed: " + str(mid) + " " + str(granted_qos))

    def on_message(self, mqttc, userdata, msg):
        self.startEvent.clear()
        self.modBusEv.clear()
        try:
            topic = self.of(msg.topic)
            if 'Modbus' in topic:
                mbCommand = msg.payload.decode()
                opCode = '07'
                pLen = bytearray(3)
                pLen[0]=int(len(mbCommand)/2)
                pL = opCode + make_two_bit(hex(pLen[0]).split('x')[1]) + \
                    make_two_bit(hex(pLen[1]).split('x')[1])+ make_two_bit(hex(pLen[2]).split('x')[1])+\
                    mbCommand
                size = len(pL)
                data=bytes.fromhex(pL)
                out = self.sock.send_message(data, size)
            elif ('Tros3' in topic)and('Command' in topic):
                #
                # ModBus ВМЕСТО DALI!!!!!!!!!
                #
                for prov in self.modbusProviders:
                    if int(topic[5]) in prov.dev['dev']['id'] :
                        if prov.dev['dev']['type'] == 'DimmingLight':
                            pass
                        elif prov.dev['dev']['type'] == 'SwitchingLight':
                            # grList = []  #список групп
                            clf=0

                            if int(topic[6]) == 3 or int(topic[6]) == 0:
                                # set isOn command
                                dd_ = VariableTRS3(VariableReader(msg.payload)).value
                                if dd_ is True:
                                    dd = True


                            elif int(topic[6]) == 4 or int(topic[6]) == 1:
                                # isOff

                                dd_ = VariableTRS3(VariableReader(msg.payload)).value
                                if dd_ is True:
                                    dd = False
                                    # clf =1


                            prov.callModBus(dd)
                            res = prov.queryModBusState()
                            if prov.isValid:
                                if 'intRes' in res:
                                    if res['intRes'] == 1:
                                        prov.dumpMqtt(data=True, fl=2)
                                    elif res['intRes'] == 0:
                                        prov.dumpMqtt(data=False, fl=2)

                            prov.dumpMqtt(data=dd, fl=2)

            elif ('Jocket' in topic) and ('Command' in topic):
                mess = json.loads(msg.payload)
                dd_ = mess['data']['value']
                dd = dd_
                for prov in self.modbusProviders:
                    if int(topic[6]) in prov.dev['dev']['id']:
                        prov.callModBus(dd)
                        res = prov.queryModBusState()
                        if prov.isValid:
                            if 'intRes' in res:
                                if res['intRes'] == 1:
                                    prov.dumpMqtt(data=True, fl=2)
                                elif res['intRes'] == 0:
                                    prov.dumpMqtt(data=False, fl=2)

                        prov.dumpMqtt(data=dd, fl=2)


        except BaseException as ex:
            logging.exception(ex)
        self.startEvent.set()
        self.modBusEv.set()

    def of(self, topic):
        arr = topic.split('/')
        return arr

    def queryOfDaliDevice(self, daliDev):
        # query state
        dd = ShortDaliAddtessComm(daliDev.dadr, QUERY_STATE, 1)

        daliDev.answerIs = False
        daliDev.typeOfQuery = 1  # 8 bit answer is needed
        daliDev.twoByteAnswer = None
        daliDev.oneByteAnswer = None

        self.isDaliQueried = True
        self.callDaliProvider = daliDev
        self.callDaliTime = daliDev.callDali(data=dd)

        while (daliDev.getCallTime != 0) and \
                ((current_milli_time() - daliDev.getCallTime) < (DALI_GAP + 50)) and \
                self.daliAnswer != 0:

            if daliDev.answerIs:
                print('answerIs = True')
                break
        if daliDev.answerIs and self.daliAnswer != 0:  # success
            # state = bitstring.BitArray(hex(int(prov.state, 16)))
            state = copy.deepcopy(daliDev.state)
            daliDev.dumpMqtt(data=state[5], fl=1, comm=2)

        else:  # no answer
            daliDev.state = None
            daliDev.isValid = False
            daliDev.dumpMqtt(data=None, fl=1, comm=2, flInvalid=True)

        if daliDev.isValid == True and daliDev.dev['type'] == 'DimmingLight':
            # query level
            dd = ShortDaliAddtessComm(daliDev.dadr, QUERY_ACTUAL_LEVEL, 1)

            daliDev.answerIs = False
            daliDev.typeOfQuery = 1  # 8 bit answer is needed
            daliDev.twoByteAnswer = None
            daliDev.oneByteAnswer = None

            self.isDaliQueried = True
            self.callDaliProvider = daliDev
            self.callDaliTime = daliDev.callDali(data=dd)

            while (daliDev.getCallTime != 0) and \
                    ((current_milli_time() - daliDev.getCallTime) < (DALI_GAP + 50)) and \
                    self.daliAnswer != 0:

                if daliDev.answerIs:
                    print('answerIs = True')
                    break
            if daliDev.answerIs and self.daliAnswer != 0:
                # success
                # prov.dumpMqtt(data=prov.state)
                daliDev.dumpMqtt(data=int(daliDev.state.uint / 254 * 100), comm=4)
            else:  # no answer
                daliDev.state = None
                daliDev.isValid = False

    def queryDali(self, starTime, dev):
        if dev.fadeTime == 0:
            delta = MIN_FADE_TIME
        else:
            delta = dev.fadeTime
        while True:
            self.queryOfDaliDevice(dev)
            if (current_milli_time() - starTime) > delta*1000:
                break

    def start_dali(self):

        for prov  in self.modbusProviders:
            # query state
            res = prov.queryModBusState()
            if prov.isValid:
                if 'intRes' in res:
                    if res['intRes'] ==1:
                        prov.dumpMqtt(data=True, fl=2)
                    elif res['intRes'] == 0:
                        prov.dumpMqtt(data=False, fl=2)

            # # query groups
            # if prov.isValid:
            #     if prov.dev['type'] == 'DimmingLight':
            #         dd= ShortDaliAddtessComm(prov.dadr, QUERY_FADE_TIME, 1)
            #
            #         prov.answerIs = False
            #         prov.typeOfQuery = 1  # 8 bit answer is needed
            #         prov.twoByteAnswer = None
            #         prov.oneByteAnswer = None
            #
            #         self.callDaliTime = prov.callDali(data=dd)
            #         self.isDaliQueried = True
            #
            #         self.callDaliProvider = prov
            #         while (prov.getCallTime != 0) and \
            #                 ((current_milli_time() - prov.getCallTime) < (DALI_GAP + 50)) and \
            #                 self.daliAnswer != 0:
            #
            #             if prov.answerIs:
            #                 print('answerIs = True')
            #                 break
            #         if prov.answerIs and self.daliAnswer != 0:
            #             fTime = prov.state[:4].uint
            #             prov.fadeTime = math.sqrt(2**fTime)/2.
            #
            #
            #             # success
            #         else:
            #             prov.isValid = False
            #             # no answer
            #             pass
            #
            #     dd= ShortDaliAddtessComm(prov.dadr, QUERY_GROU_811, 1)
            #
            #     prov.answerIs = False
            #     prov.typeOfQuery = 1  # 8 bit answer is needed
            #     prov.twoByteAnswer = None
            #     prov.oneByteAnswer = None
            #
            #     self.callDaliTime = prov.callDali(data=dd)
            #     self.isDaliQueried = True
            #
            #     self.callDaliProvider = prov
            #     while (prov.getCallTime != 0) and \
            #             ((current_milli_time() - prov.getCallTime) < (DALI_GAP + 50)) and \
            #             self.daliAnswer != 0:
            #
            #         if prov.answerIs:
            #             print('answerIs = True')
            #             break
            #     if prov.answerIs and self.daliAnswer != 0:
            #         prov.group2 = copy.deepcopy(prov.state)
            #         prov.groupList = list(prov.group2)
            #
            #
            #         # success
            #     else:
            #         prov.isValid = False
            #         # no answer
            #         pass
            #     #######################################
            #     dd = ShortDaliAddtessComm(prov.dadr, QUERY_GROU_07, 1)
            #
            #     prov.answerIs = False
            #     prov.typeOfQuery = 1  # 8 bit answer is needed
            #     prov.twoByteAnswer = None
            #     prov.oneByteAnswer = None
            #
            #     self.callDaliTime = prov.callDali(data=dd)
            #     self.isDaliQueried = True
            #
            #     self.callDaliProvider = prov
            #     while (prov.getCallTime != 0) and \
            #             ((current_milli_time() - prov.getCallTime) < (DALI_GAP + 50)) and \
            #             self.daliAnswer != 0:
            #
            #         if prov.answerIs:
            #             print('answerIs = True')
            #             break
            #     if prov.answerIs and self.daliAnswer != 0:
            #         prov.group1 = copy.deepcopy(prov.state)
            #         prov.groupList.extend(list(prov.group1))
            #         prov.groupList.reverse()
            #         # success
            #     else:
            #         prov.isValid = False
            #         # no answer
            #     if prov.isValid:
            #
            #         n=0
            #         for grp in prov.groupList:
            #             if grp:
            #                 self.daliGroup[n].append(prov)
            #             n=n+1

    def rpg_listen_fun(self):

        data = '07050000E103824200' #запрос настроек канала 00
        # data = '07080000E103824000040000' #установка скорости 19200 на 00 канале
        size = len(data)
        data = bytes.fromhex(data)
        device =self.sock
        try:
            out = device.send_message(data, size)
            print('запрос на состояние модуля 1 ModBus: {0}'.format(data))

        except BaseException as ex:
            logging.exception(ex)
            self.mqttc.publish(topic=topic_dump.format(BUS_ID) + '/error', payload=str(ex))
        else:
            try:
                self._start_time = time.time()
            # out = VariableTRS3(None, int(BUS_ID), 0, tk)
            # top_out = topic_dump.format(PROJECT, BUS_ID, '0')
            # self.mqttc.publish(topic=topic_dump.format(PROJECT, BUS_ID, '0'), payload=out.pack())


            except BaseException as ex:
                logging.exception(ex)

    def test_dali_num(self):
        for i in range(0, 10):
            time.sleep(1)
            print('id={0}'.format(i))

            ii = hex(int((bin(i) + '1'), 2))
            ii = ii[2:]
            if len(ii) == 1:
                ii = '0' + ii
            print('ii={0}'.format(ii))

            data = '07 07 00 00 E1 03 01 04 01 {0} A0'.format(ii).replace(' ', '')
            # data = '07 07 00 00 E2 03 01 00 01 FE 00'

            size = len(data)
            data = bytes.fromhex(data)
            device=self.sock
            try:
                out = device.send_message(data, size)
                print('запрос на состояние модуля {0} DALI: {1}'.format(ii, data))

            except BaseException as ex:
                logging.exception(ex)
                self.mqttc.publish(topic=topic_dump[1].format(BUS_ID) + '/error', payload=str(ex))
            else:
                # print('ответ: {0}'.format(out))
                print('====================================================================================')
                # self._start_time = time.time()
                # out = VariableTRS3(None, int(BUS_ID), 0, tk)
                # top_out = topic_dump.format(PROJECT, BUS_ID, '0')
                # self.mqttc.publish(topic=topic_dump.format(PROJECT, BUS_ID, '0'), payload=out.pack())
                # logging.debug('[  <-]: {}'.format(out))



    def listen_rpg1(self, startEv):

        device = self.sock
        while True:
            # startEv.wait()
            try:
                out = device.recive_data()
                    # if out:
                    #     break
                    #
                    # logging.debug('[  <-]: {}'.format(out))
            except BaseException as ex:
                # logging.exception(ex)
                self.mqttc.publish(topic=topic_dump[1].format(BUS_ID) + '/error', payload=str(ex))
            else:
                if out is not None:
                    while len(out) > 0:
                        rpgData, rest = self.parceData(out)
                        if hex(rpgData['opCode']) == OPCODECANDATA:
                            self.parceCAN(rpgData['payloadCAN'])
                            # print('===={0}========={1}========'.format(hex(rpgData['payloadCAN']['canId'][0]), hex(rpgData['payloadCAN']['canId'][1])))
                        elif hex(rpgData['opCode']) == OPCODEPINGREQ:
                            print("04 00 00 00")
                        elif hex(rpgData['opCode']) == OPCODECONNECT:
                            print("RPG GATEWAY IS CONNECTED")
                        if len(rest) == 0:
                            break
                        out = out[(len(out)-len(rest)):]
                    #
                    # self.mqttc.publish(topic=topic_send[1] + '/lamp', payload=str(out))
                    # logging.debug('[recive from server  <-]: {}'.format(out))
    def parceCAN(self, data):
        canId=bytearray(2)
        canId[0]=data['canId'][1]
        canId[1]=data['canId'][0]
        canData = bitstring.BitArray(canId)
        c=canData.bin
        addr_to = c[-5:]
        addr_from =c[:-5]
        addrIntTo = canData[-5:].uint
        addrIntFrom = canData[:-5].uint
        if addrIntTo == 31:
            #  message to gateway
            byte0 = bytearray(1)
            byte0[0] = data['data'].pop(0)
            bbyte0 = bitstring.BitArray(byte0)
            flag_res = bbyte0[1]
            t_class = bbyte0[-5:]
            n = t_class.int
            if n == 2:
                #  ModBus
                modBus = data['data']
                bbyte1 = bitstring.BitArray(hex(data['data'][0]))
                byte1 = bitstring.BitArray(8 - bbyte1.len)
                byte1.append(bbyte1)
                if byte1[4] is not True:   #   CMD or not CMD
                    if byte1[5] is not True:  #   PART or not PART
                        mbchann_ = byte1[-2:]
                        mbchann = mbchann_.uint
                        maddr = modBus[1]
                        fcode = hex(modBus[2])
                        nbite = modBus[3]
                        modBusData = modBus[4:(4+nbite)]
                        print(':::modbus byte1 = {0} chann={1} id={2} fcode={3} nbite={4} data = {5}'.format(byte1.bin, mbchann_.bin, maddr, \
                                                                                       str(fcode), nbite, str(modBusData)))
                        for dev in self.modbusProviders:
                            if dev.channel == mbchann and dev.maddr == maddr:
                                dev.setValue(modBusData)
                                dev.getAnswer(modBusData)
                                dev.work()

                                pass
                # self.mqttc.publish(topic= topic_dump[2], payload=str(modBus), qos=1, retain=True)
                print('===========mbus======={}'.format(str(modBus)))

            elif n==1:
                #  Dali
                # if (current_milli_time()-self.callDaliTime)<= DALI_GAP:
                    bbyte1 = bitstring.BitArray(hex(data['data'][0]))
                    byte1=bitstring.BitArray(8-bbyte1.len)
                    byte1.append(bbyte1)

                    if byte1[2] is not True:
                        bfl = bitstring.BitArray(6)
                        bfl.append(byte1[3:5])
                        fl=bfl.int
                        b_chann = bitstring.BitArray(5)
                        b_chann.append(byte1[5:])
                        i_chann=b_chann.int

                        if fl == 0:
                            # 8 bit anser
                            daliData =bitstring.BitArray(hex(data['data'][1]))

                            print('dali 1 byte answer {}'.format(daliData.bin))

                            if (self.callDaliProvider.typeOfQuery == 1) and \
                                    (self.callDaliProvider.oneByteAnswer is None) and \
                                    (self.callDaliProvider.twoByteAnswer is not None):
                                self.callDaliProvider.oneByteAnswer = daliData
                                self.callDaliProvider.getAnswer(daliData)
                                dataDali = bitstring.BitArray(8-daliData.length)
                                dataDali.append(daliData)
                                self.callDaliProvider.setValue(dataDali)
                                # self.callDaliProvider.dumpMqtt(dataDali)
                                self.daliAnswer = 1
                                self.callDaliProvider.isValid = True
                            elif (self.callDaliProvider.typeOfQuery != 1):
                                print('no answer needed')
                                self.daliAnswer = -1

                            elif (self.callDaliProvider.twoByteAnswer is None):
                                print ('no echo from dali - only 8 bit')
                                self.daliAnswer = -2

                            elif (self.callDaliProvider.oneByteAnswer is not None):
                                print ('8 bit answer is already on')

                            self.isDaliQueried = False
                            # jocket = VariableJocket.create_data(3171, 31090132,
                            #                                     'set', int(dataDali, 16), "{00000000-0000-0000-0000-000000000000}")
                            # self.mqttc.publish(topic=topic_dump[3], payload=jocket.pack(), qos=1, retain=True)

                        elif fl == 2: # no anser
                            #daliData = data['data'][1]
                            if (self.callDaliProvider is not None):
                                self.callDaliProvider.getAnswer('no answer from dali')
                                self.callDaliProvider.Value = None
                                self.callDaliProvider.oneByteAnswer = None
                                self.callDaliProvider.twoByteAnswer = None
                                self.callDaliProvider.isValid = False

                            self.daliAnswer = 0
                            self.isDaliQueried = False

                            print('нет ответа от Dali')
                        elif fl == 1:
                            # 2 byte
                            daliData = data['data'][1:]
                            self.callDaliProvider.twoByteAnswer = daliData
                            if (self.callDaliProvider.typeOfQuery == 0):
                                self.callDaliProvider.getAnswer(daliData)
                                self.daliAnswer = 1
                                self.isDaliQueried = False
                                self.callDaliProvider.isValid = True
                            print('dali 2 byte answer == {}'.format(str(daliData)))
                            # self.mqttc.publish(topic=topic_dump[3], payload=str(daliData)[:2], qos=1, retain=True)
                    else:
                        #  error on dali
                        self.daliAnswer = -3
                        self.isDaliQueried = False
                        print('!!!!!!!!!!!   Dali error      !!!!!!!!!')

                        if (self.callDaliProvider is not None):
                            self.callDaliProvider.getAnswer('!!!!!!!!!!!   Dali error      !!!!!!!!!')
                            self.callDaliProvider.Value = None
                            self.callDaliProvider.oneByteAnswer = None
                            self.callDaliProvider.twoByteAnswer = None
                            self.callDaliProvider.isValid = False
                # else:
                #     self.daliAnswer = -4




    def parceData(self, message):
        dataAr = list(bytearray(0))
        for b in message:
            dataAr.append(b)

        if hex(dataAr[0]) == OPCODECANDATA:
            data = {
                'opCode': bytearray(1),
                'payloadLen': bytearray(3),
                'payloadCAN': {
                    'canId': bytearray(2),
                    'dlc': bytearray(1),
                    'data': bytearray(8)
                }
            }
            data['opCode']=dataAr.pop(0)
            for i in range(3):
                data['payloadLen'][i]= dataAr.pop(0)

            for i in range(2):
                data['payloadCAN']['canId'][i]= dataAr.pop(0)

            data['payloadCAN']['dlc'] = data['payloadLen'][0]-2

            for i in range(int(data['payloadLen'][0])-2):
                data['payloadCAN']['data'][i]=dataAr.pop(0)

            return data, dataAr

        elif hex(dataAr[0]) == OPCODECONNECT:
            toconnect = {
                'opCode': bytearray(1),
                'payloadLen': bytearray(3),
                'payload': bytearray(8)
            }
            toconnect['opCode'] = dataAr.pop(0)
            for i in range(3):
                toconnect['payloadLen'][i] = dataAr.pop(0)
            for i in range(int(toconnect['payloadLen'][0])):
                toconnect['payload'][i]=dataAr.pop(0)

            return toconnect, dataAr

        elif (hex(dataAr[0]) == OPCODEPINGREG) or (hex(dataAr[0]) == OPCODEPINGREQ):
            ping = {
                'opCode': bytearray(1),
                'payloadLen': bytearray(3)
            }
            ping['opCode'] = dataAr.pop(0)
            for i in range(3):
                ping['payloadLen'][i] = dataAr.pop(0)
            return ping, dataAr
        elif hex(dataAr[0]) == OPCODEDISCONNECT:
            disconnect = {
                'opCode': bytearray(1),
            }
            disconnect['opCode'] = dataAr.pop(0)

            return disconnect, dataAr

        elif hex(dataAr[0]) == OPCODEERROR:
            error = {
                'opCode': bytearray(1),
                'payloadLen': bytearray(3),
                'error': bytearray(1)
            }
            error['opCode']= dataAr.pop(0)
            for i in range(3):
                error['payloadLen'][i] = dataAr.pop(0)
            error['error'] = dataAr.pop(0)
            return error, dataAr



    def write_to_bro(self, topId, num, value):
        out = VariableTRS3(None, topId, num, value)
        self.mqttc.publish(topic=topic_dump.format(PROJECT, str(topId), str(num)), payload=out.pack())
        logging.debug('[  <-]: {}'.format(out))

    def modbusQuery(self, event):
        while True:
            time.sleep(60)
            event.wait()
            # for prov in self.modbusProviders:
            #     if (current_milli_time() - prov.getCallTime)>= prov.time_gap:
            #         prov.callModBus()

    def askTempr(self):
        device = self.sock
        while True:
            # time.sleep(1)    10 03 01 02 00 02 - команда чтения температуры
            # self._command_event.wait()

            time.sleep(2)

            # for data in device.commands():
            data = '07 0A 00 00 E1 03 02 00 10 03 01 02 00 02'
            size = len(data.strip())
            data = bytes.fromhex(data.strip())
            try:
                out = device.send_message(data, size)

            except BaseException as ex:
                logging.exception(ex)
                # self.mqttc.publish(topic=topic_dump.format(BUS_ID) + '/error', payload=str(ex))


    def listen_rpg(self, startEvent):
        while True:
            # time.sleep(1)    10 03 01 02 00 02 - команда чтения температуры
            # self._command_event.wait()

            startEvent.wait()
            if (time.time()- self._start_time) >= 5.:

                device = self.sock
                # for data in device.commands():
                data = '03000000'
                size=len(data)
                data = bytes.fromhex(data)
                try:
                    out = device.send_message(data, size)
                    # print(data)
                except BaseException as ex:
                    logging.exception(ex)
                    self.mqttc.publish(topic=topic_dump[1].format(BUS_ID) + '/error', payload=str(ex))
                else:
                    try:
                        self._start_time=time.time()
                       # out = VariableTRS3(None, int(BUS_ID), 0, tk)
                       # top_out = topic_dump.format(PROJECT, BUS_ID, '0')
                       # self.mqttc.publish(topic=topic_dump.format(PROJECT, BUS_ID, '0'), payload=out.pack())
                       # logging.debug('[  <-]: {}'.format(out))

                    except BaseException as ex:
                        logging.exception(ex)

    #    self._step_event.clear()

    def connect_rpg(self):

        device = self.sock
        # for data in device.commands():
        data = '0104000001001027'
        size = len(data)
        data = bytes.fromhex(data)
        try:
            out = device.send_message(data, size)
            print(data)
        except BaseException as ex:
            logging.exception(ex)
            # self.mqttc.publish(topic=topic_dump.format(BUS_ID) + '/error', payload=str(ex))
        else:
            try:
                self._start_time = time.time()
                # out = VariableTRS3(None, int(BUS_ID), 0, tk)
                # top_out = topic_dump.format(PROJECT, BUS_ID, '0')
                # self.mqttc.publish(topic=topic_dump.format(PROJECT, BUS_ID, '0'), payload=out.pack())
                # logging.debug('[  <-]: {}'.format(out))

            except BaseException as ex:
                logging.exception(ex)





def run():
    RGPTCPAdapterLauncher().start()




if __name__ == '__main__':
    run()
    # TCPAdapterLauncher()
