import socket
import threading
import time
import paho.mqtt.client
from threading import Timer
import bitstring
from bitstring import BitArray
import array

from spread_core.mqtt.variables import VariableTRS3, VariableReader
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
DALI_GAP = 100

MODBUS_DEV = config['MODBUS_DEV']
DALI_DEV = config['DALI_DEV']

# topic_dump = 'Tros3/State/{}/{}/{}'
# topic_send = 'ModBus/from_Client/{}'
topic_send =config['TOPIC_SEND']
topic_dump = config['TOPIC_DUMP']

is_lock=False

current_milli_time = lambda: int(round(time.time() * 1000))

def make_two_bit(x):
    bytes_list =list('00')
    list_x = list(x)
    i=-1
    while abs(i) <= len(x):
        bytes_list[i]=list_x[i]
        i=i-1
    return ''.join(bytes_list)

class DaliProvider:
    def __init__(self, rpgClient, mqtt, *args):
        self._socket = rpgClient
        self.dev = args[0]
        self._mqtt = mqtt
        self._callDTime = 0
        self.state = None
        self.isValid = None
        self.oneByteAnswer = None
        self.twoByteAnswer = None
        self.typeOfQuery = None # 0 - no answer, 1 - need answer
        self.group = None
        self._call = None
        self.answerIs = False
        self.dadr = args[0]['dadr']
        self._stateTopic = 'Tros3/State/{}/Equipment/{}/{}/'.format(PROJECT, args[0]['type'], args[0]['id'])
        self.answer = None


    def setValue(self, val):
        self.state = val

    @property
    def getCallTime(self):
        return self._callDTime

    def getAnswer(self, data):
        print('dali answer is {}'.format(str(data)))
        self.answerIs = True
        pass

    def askLevel(self):
        pass

    def askGroup(self):
        pass

    def setLevel(self, data):
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
        self._socket.send_message(data, size)
        self.answerIs=False
        return self._callDTime

    def callDali(self, data):
        self._call = data
        mbCommand = 'E203010001' + data
        opCode = '07'
        pLen = bytearray(3)
        pLen[0] = int(len(mbCommand) / 2)
        pL = opCode + make_two_bit(hex(pLen[0]).split('x')[1]) + \
             make_two_bit(hex(pLen[1]).split('x')[1]) + make_two_bit(hex(pLen[2]).split('x')[1]) + \
             mbCommand
        size = len(pL)
        dd = bytes.fromhex(pL)
        self._callDTime = current_milli_time()
        self._socket.send_message(dd, size)
        self.answerIs=False
        return self._callDTime

    def dumpMqtt(self, data):
        out = VariableTRS3(None, self.dev['id'], 0, data)
        self._mqtt.publish(topic=self._stateTopic, payload=out.pack(), qos=1, retain=True)

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
        #out = b''
        self.sock.send(data)
        print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
        logging.debug('[->  ]: {}'.format(' '.join(hex(b)[2:].rjust(2, '0').upper() for b in data)))
        print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')


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
        self.daliAnswer=None   # 0 - no answer,
                                # 1 - ok,
        #                        -1 - 8 bit answer - no needed answer,
        #                        -2 - 8 bit answer - no echo from dali
        #                        -3 - error on dali line
        self.isDaliQueried = False
        self.modbusAnswer = False
        self.callDaliProvider = None

        for topic in topic_send:
            self.mqttc.subscribe(topic)
            logging.debug('Subscribed to {}'.format(topic))

        for prov in DALI_DEV:
            daliDev = DaliProvider(self.sock, self.mqttc, prov)
            self.daliProviders.append(daliDev)




    def start(self):
        self._command_event.set()
        self.connect_rpg()
        # self.rpg_listen_fun()
        listen = threading.Thread(target=self.listen_rpg)
        listen1 = threading.Thread(target=self.listen_rpg1)
        listen2 = threading.Thread(target=self.askTempr)



        listen.start()
        listen1.start()

        # listen2.start()
        self.start_dali()
        self.mqttc.loop_forever()

        # self.test_dali_num()

    def on_connect(self, mqttc, userdata, flags, rc):
        if rc==0:
            print("connected OK Returned code=",rc)
        else:
            print("Bad connection Returned code=",rc)

    def on_subscribe(self, mqttc, userdata, mid, granted_qos):
        print("Subscribed: " + str(mid) + " " + str(granted_qos))

    def on_message(self, mqttc, userdata, msg):

        try:
            topic = self.of(msg.topic)
            if topic[2]=='Modbus':
                mbCommand = msg.payload.decode()
                opCode = '07'
                pLen = bytearray(3)
                pLen[0]=int(len(mbCommand)/2)
                pL = opCode + make_two_bit(hex(pLen[0]).split('x')[1]) + \
                    make_two_bit(hex(pLen[1]).split('x')[1])+ make_two_bit(hex(pLen[2]).split('x')[1])+\
                    mbCommand
                size = len(pL)
                data=bytes.fromhex(pL)
                self.sock.send_message(data, size)
            elif ('Tros3' in  topic) and ('Command' in topic):
                # mbCommand = 'E203010001'+msg.payload.decode().split('#')[0]
                # opCode = '07'
                # pLen = bytearray(3)
                # pLen[0]=int(len(mbCommand)/2)
                # pL = opCode + make_two_bit(hex(pLen[0]).split('x')[1]) + \
                #     make_two_bit(hex(pLen[1]).split('x')[1])+ make_two_bit(hex(pLen[2]).split('x')[1])+\
                #     mbCommand
                # size = len(pL)
                # data=bytes.fromhex(pL)
                # self.sock.send_message(data, size)
                for prov in self.daliProviders:
                    if prov.dev['id'] == topic[5]:
                        self.callDaliTime = prov.callDali(VariableTRS3(VariableReader(msg.payload))['value'])
                        self.callDaliProvider = prov
                        while (prov.getCallTime != 0) and (current_milli_time()-prov.getCallTime < 100):
                            if prov.answerIs:
                                break
                        if prov.answerIs:
                            # success
                            pass
                        else:
                            # no answer
                            pass

        except BaseException as ex:
            logging.exception(ex)

    def of(self, topic):
        arr = topic.split('/')
        return arr

    def start_dali(self):

        for prov  in self.daliProviders:

            dd = QUERY_ACTUAL_LEVEL
            devaddr=bitstring.BitArray(hex(prov.dadr))
            daddr = bitstring.BitArray(6 - devaddr.length)
            daddr.append(devaddr)
            addrbyte = bitstring.BitArray(bin(0))
            addrbyte.append(daddr)
            addrbyte.append(bitstring.BitArray(bin(1)))
            dd = addrbyte.hex + dd
            prov.answerIs = False
            prov.typeOfQuery = 1      # 8 bit answer is needed
            prov.twoByteAnswer = None
            prov.oneByteAnswer = None

            self.callDaliTime = prov.callDali(dd)
            self.isDaliQueried = True

            self.callDaliProvider = prov
            while (prov.getCallTime != 0) and ((current_milli_time() - prov.getCallTime) < (DALI_GAP+50)):

                if prov.answerIs:
                    print('answerIs = True')
                    break
            if prov.answerIs:

                # success
                pass
            else:
                # no answer
                pass

    def rpg_listen_fun(self):

        data = '07050000E103824200' #запрос настроек канала 00
        # data = '07080000E103824000040000' #установка скорости 19200 на 00 канале
        size = len(data)
        data = bytes.fromhex(data)
        device =self.sock
        try:
            device.send_message(data, size)
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
                device.send_message(data, size)
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



    def listen_rpg1(self):


        while True:
            device = self.sock
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
                self.mqttc.publish(topic= topic_dump[2], payload=str(modBus), qos=1, retain=True)
                print('::::::::::::::::::::: modbus = {0}'.format(str(data['data'])))
            elif n==1:
                #  Dali
                if (current_milli_time()-self.callDaliTime)<= DALI_GAP:
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
                            daliData =data['data'][1]

                            print('dali 1 byte answer {}'.format(str(daliData)))

                            if (self.callDaliProvider.typeOfQuery == 1) and \
                                    (self.callDaliProvider.oneByteAnswer is None) and \
                                    (self.callDaliProvider.twoByteAnswer is not None):
                                self.callDaliProvider.oneByteAnswer = daliData
                                self.callDaliProvider.getAnswer(daliData)
                                dataDali = str(daliData)[:2]
                                self.callDaliProvider.Value(dataDali)
                                self.callDaliProvider.dumpMqtt(dataDali)
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
                device.send_message(data, size)

            except BaseException as ex:
                logging.exception(ex)
                # self.mqttc.publish(topic=topic_dump.format(BUS_ID) + '/error', payload=str(ex))


    def listen_rpg(self):
        while True:
            # time.sleep(1)    10 03 01 02 00 02 - команда чтения температуры
            # self._command_event.wait()


            if (time.time()- self._start_time) >= 5.:

                device = self.sock
                # for data in device.commands():
                data = '03000000'
                size=len(data)
                data = bytes.fromhex(data)
                try:
                    device.send_message(data, size)
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
