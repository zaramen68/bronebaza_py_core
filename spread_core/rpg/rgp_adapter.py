import socket
import threading
import queue
import time
import math
import paho.mqtt.client
from threading import Timer
import bitstring
import copy



from spread_core.mqtt.variables import VariableTRS3, VariableReader


from spread_core.tools.settings import logging



from spread_core.rpg.protocol import *
from spread_core.rpg.settings import *

from spread_core.rpg.diprovider import DiProvider
from spread_core.rpg.modbus_provder import ModBusProvider
from spread_core.rpg.dali_provider import DaliProvider
from spread_core.rpg.blackout import Blackout



topic_dump = 'Tros3/{}'


is_lock=False

# current_milli_time = lambda: int(round(time.time() * 1000))



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
    diQueue = queue.Queue()
    diMask = dict()
    diBlackOut = []

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
        self.diProviders = []
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
        self.startEvent = threading.Event()
        self.startListenEvent = threading.Event()
        self.qFl = threading.Event()
        self.diListenEvent=threading.Event()


        for prov in DALI_DEV:
            daliDev = DaliProvider(self.sock, self.mqttc, prov)
            self.daliProviders.append(daliDev)

        for prov in MODBUS_DEV:
            modbusDev = ModBusProvider(self.sock, self.mqttc, prov)
            self.modbusProviders.append(modbusDev)

        for prov in DI_DEV:
            diDev = DiProvider(self.sock, self.mqttc, prov)
            self.diProviders.append(diDev)
            if diDev.classF == 'blackout':
                self.diMask[str(diDev.topicIn)]=[diDev.dev['dev']['type'], None]
                self.diBlackOut.append(diDev)

        topic = 'Tros3/Command/{}/#'.format(PROJECT)
        self.mqttc.subscribe(topic)
        logging.debug('Subscribed to {}'.format(topic))


    def start(self):
        self._command_event.set()
        self.connect_rpg()
        # self.rpg_listen_fun()

        listen = threading.Thread(target=self.listen_rpg, args=(self.startEvent,))
        listen1 = threading.Thread(target=self.listen_rpg1, args=(self.diQueue, self.startListenEvent, self.diListenEvent))
        listen2 = threading.Thread(target=self.modbusQuery, args=(self.startEvent,))
        listen3 = threading.Thread(target=self.listenDI, args=(self.diQueue, self.diListenEvent, self.diMask, self.diBlackOut, self.daliProviders))



        listen.start()
        listen1.start()

        self.startListenEvent.set()

        self.start_dali()
        self.startDi()

        listen3.start()
        listen2.start()
        self.startEvent.set()
        self.qFl.set()
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
                self.sock.send_message(data, size)
            elif ('Tros3' in topic)and('Command' in topic):

                for prov in self.daliProviders:
                    if prov.dev['id'] == int(topic[3]):
                        if prov.dev['type'] == 'DimmingLight':
                            grList = []  #список групп
                            clf=0
                            if int(topic[4]) == 7:
                                # set group level command

                                dd_ = VariableTRS3(VariableReader(msg.payload)).value
                                dd=int(dd_/100*254)
                            elif int(topic[4]) == 5:  # isOn command

                                dd_ = VariableTRS3(VariableReader(msg.payload)).value
                                if dd_ is True:
                                    dd = 254

                            elif int(topic[4]) == 6:  # isOff

                                dd_ = VariableTRS3(VariableReader(msg.payload)).value
                                if dd_ is True:
                                    dd = 0
                                    clf =1
                            n=0
                            for gr in prov.groupList:
                                if gr:
                                    grComm = GroupDaliAddtessComm(n, dd, clf)
                                    grList.append(n)

                                    prov.answerIs = False
                                    prov.typeOfQuery = 0  # no answer
                                    prov.twoByteAnswer = None
                                    prov.oneByteAnswer = None
                                    self.isDaliQueried = True
                                    self.callDaliTime = prov.callDali(grComm)
                                    self.callDaliProvider = prov
                                    while (prov.getCallTime != 0) and (current_milli_time()-prov.getCallTime < DALI_GAP):
                                        if prov.answerIs:
                                            break

                                n=n+1

                            qList = []
                            for gr in grList:
                                qList = qList+self.daliGroup[gr]
                            qList = list(set(qList))    # формирование списка DALI устройств для опроса

                            self.startEvent.clear()
                            self.startListenEvent.clear()
                            self.qFl.set()
                            for daliDevice in qList:
                                t=threading.Thread(target=self.queryDali,
                                                   args= (daliDevice.getCallTime, daliDevice, self.qFl, self.diListenEvent, self.diQueue))
                                t.start()
                                # t.join()

                            self.qFl.clear()
                            self.startEvent.set()
                            self.startListenEvent.set()
                                # self.queryDali(daliDevice.getCallTime, daliDevice)

                        elif prov.dev['type'] == 'SwitchingLight':
                            grList = []  #список групп
                            clf=0

                            if int(topic[4]) == 3:
                                # set isOn command
                                dd_ = VariableTRS3(VariableReader(msg.payload)).value
                                if dd_ is True:
                                    dd = 254


                            elif int(topic[4]) == 4:
                                # isOff

                                dd_ = VariableTRS3(VariableReader(msg.payload)).value
                                if dd_ is True:
                                    dd = 0
                                    clf =1

                            n=0
                            for gr in prov.groupList:
                                if gr:
                                    grComm = GroupDaliAddtessComm(n, dd, clf)
                                    grList.append(n)

                                    prov.answerIs = False
                                    prov.typeOfQuery = 0  # no answer
                                    prov.twoByteAnswer = None
                                    prov.oneByteAnswer = None
                                    self.isDaliQueried = True
                                    self.callDaliTime = prov.callDali(grComm)
                                    self.callDaliProvider = prov
                                    while (prov.getCallTime != 0) and (current_milli_time()-prov.getCallTime < DALI_GAP):
                                        if prov.answerIs:
                                            break

                                n=n+1

                            qList = []
                            for gr in grList:
                                qList = qList+self.daliGroup[gr]
                            qList = list(set(qList))    # формирование списка DALI устройств для опроса
                            self.startEvent.clear()
                            self.startListenEvent.clear()
                            self.qFl.set()

                            for daliDevice in qList:
                                t=threading.Thread(target=self.queryDali,
                                                   args=(daliDevice.getCallTime, daliDevice, self.qFl, self.diListenEvent, self.diQueue))
                                t.start()
                                # t.join()

                            self.qFl.clear()
                            self.startEvent.set()
                            self.startListenEvent.set()


                                # self.queryDali(daliDevice.getCallTime, daliDevice)


        except BaseException as ex:
            logging.exception(ex)

    def of(self, topic):
        arr = topic.split('/')
        return arr

    def queryOfDaliDevice(self, daliDev, diQue=None, diEv=None):

        dd = ShortDaliAddtessComm(daliDev.dadr, QUERY_STATE, 1)

        daliDev.answerIs = False
        daliDev.typeOfQuery = 1  # 8 bit answer is needed
        daliDev.twoByteAnswer = None
        daliDev.oneByteAnswer = None

        self.isDaliQueried = True
        self.callDaliProvider = daliDev
        self.daliAnswer = None
        self.callDaliTime = daliDev.callDali(data=dd, resp=True)


        while (daliDev.getCallTime != 0) and \
                ((current_milli_time() - daliDev.getCallTime) < (DALI_GAP + 50)) and \
                self.daliAnswer == None:

            self.reciveData(diEv, diQue)
            if daliDev.answerIs:
                print('answerIs = True')
                break

        if daliDev.answerIs and self.daliAnswer == 1:  # success
            # state = bitstring.BitArray(hex(int(prov.state, 16)))
            state = copy.deepcopy(daliDev.state)
            self.writeMqtt(dev=daliDev, data=state[5], fl=1, comm=2)

        else:  # no answer
            daliDev.state = None
            daliDev.isValid = False
            self.writeMqtt(dev=daliDev, data=None, fl=1, comm=2)

        if daliDev.isValid == True:
        # if daliDev.isValid == True and daliDev.dev['type'] == 'DimmingLight':
            # query level
            dd = ShortDaliAddtessComm(daliDev.dadr, QUERY_ACTUAL_LEVEL, 1)

            daliDev.answerIs = False
            daliDev.typeOfQuery = 1  # 8 bit answer is needed
            daliDev.twoByteAnswer = None
            daliDev.oneByteAnswer = None

            self.isDaliQueried = True
            self.callDaliProvider = daliDev
            self.daliAnswer = None
            self.callDaliTime = daliDev.callDali(data=dd)


            while (daliDev.getCallTime != 0) and \
                    ((current_milli_time() - daliDev.getCallTime) < (DALI_GAP + 50)) and \
                    self.daliAnswer == None:

                self.reciveData(diEv, diQue)
                if daliDev.answerIs:
                    print('answerIs = True')
                    break

            if daliDev.answerIs and self.daliAnswer == 1:
                # success
                self.writeMqtt(dev=daliDev, data=int(daliDev.state.uint / 254 * 100), comm=4)
                daliDev.lastLevel = int(daliDev.state.uint / 254 * 100)
            else:  # no answer
                daliDev.state = None
                daliDev.isValid = False


    def queryDali(self, starTime, dev, ev, diEv=None, diQue=None):

        if dev.fadeTime == 0:
            delta = MIN_FADE_TIME
        else:
            delta = dev.fadeTime

        while True:
            ev.wait()
            ev.clear()
            diEv.clear()
            self.queryOfDaliDevice(dev, diEv, diQue)
            diEv.set()
            ev.set()
            if (current_milli_time() - starTime) > delta*1000.:
                break


    def writeMqtt(self, dev, data=None, fl=None, comm=0):

        if data == None and dev.state is not None:
            data_ = dev.state
            data = data_.uint

        out = VariableTRS3(None, dev.dev['id'], comm, data)
        if fl == None:
            clientTopic = dev._stateTopicLevel
        elif fl == 1:
            clientTopic = dev._stateTopicIsOn
        self.mqttc.publish(topic=clientTopic, payload=out.pack(), qos=0, retain=True)

    def start_dali(self):

        for prov  in self.daliProviders:
            # query state
            self.queryOfDaliDevice(prov)

            # query groups
            if prov.isValid:
                if prov.dev['type'] == 'DimmingLight':
                    dd= ShortDaliAddtessComm(prov.dadr, QUERY_FADE_TIME, 1)

                    prov.answerIs = False
                    prov.typeOfQuery = 1  # 8 bit answer is needed
                    prov.twoByteAnswer = None
                    prov.oneByteAnswer = None

                    self.callDaliTime = prov.callDali(data=dd)
                    self.isDaliQueried = True

                    self.callDaliProvider = prov
                    while (prov.getCallTime != 0) and \
                            ((current_milli_time() - prov.getCallTime) < (DALI_GAP + 50)) and \
                            self.daliAnswer != 0:

                        if prov.answerIs:
                            print('answerIs = True')
                            break
                    if prov.answerIs and self.daliAnswer != 0:
                        fTime = prov.state[:4].uint
                        prov.fadeTime = math.sqrt(2**fTime)/2.


                        # success
                    else:
                        prov.isValid = False
                        # no answer
                        pass

                dd= ShortDaliAddtessComm(prov.dadr, QUERY_GROU_811, 1)

                prov.answerIs = False
                prov.typeOfQuery = 1  # 8 bit answer is needed
                prov.twoByteAnswer = None
                prov.oneByteAnswer = None

                self.callDaliTime = prov.callDali(data=dd)
                self.isDaliQueried = True

                self.callDaliProvider = prov
                while (prov.getCallTime != 0) and \
                        ((current_milli_time() - prov.getCallTime) < (DALI_GAP + 50)) and \
                        self.daliAnswer != 0:

                    if prov.answerIs:
                        print('answerIs = True')
                        break
                if prov.answerIs and self.daliAnswer != 0:
                    prov.group2 = copy.deepcopy(prov.state)
                    prov.groupList = list(prov.group2)


                    # success
                else:
                    prov.isValid = False
                    # no answer
                    pass
                #######################################
                dd = ShortDaliAddtessComm(prov.dadr, QUERY_GROU_07, 1)

                prov.answerIs = False
                prov.typeOfQuery = 1  # 8 bit answer is needed
                prov.twoByteAnswer = None
                prov.oneByteAnswer = None

                self.callDaliTime = prov.callDali(data=dd)
                self.isDaliQueried = True

                self.callDaliProvider = prov
                while (prov.getCallTime != 0) and \
                        ((current_milli_time() - prov.getCallTime) < (DALI_GAP + 50)) and \
                        self.daliAnswer != 0:

                    if prov.answerIs:
                        print('answerIs = True')
                        break
                if prov.answerIs and self.daliAnswer != 0:
                    prov.group1 = copy.deepcopy(prov.state)
                    prov.groupList.extend(list(prov.group1))
                    prov.groupList.reverse()
                    # success
                else:
                    prov.isValid = False
                    # no answer
                if prov.isValid:

                    n=0
                    for grp in prov.groupList:
                        if grp:
                            self.daliGroup[n].append(prov)
                        n=n+1


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
            self.mqttc.publish(topic=topic_dump.format(PROJECT) + '/error', payload=str(ex))
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
                self.mqttc.publish(topic=topic_dump.format(PROJECT) + '/error', payload=str(ex))
            else:
                # print('ответ: {0}'.format(out))
                print('====================================================================================')

    def listenDI(self, diQue,  ev, diMask, diList, daliList):
        blackOut = Blackout(diMask, diList, daliList)
        while True:
            ev.wait()
            while not diQue.empty():
                data = diQue.get_nowait()
                fl, res =self.workDIData(data=data)
                if fl == 1:
                    sb=bitstring.BitArray()
                    for bt in res:
                        sb_=bitstring.BitArray(hex(bt))
                        if sb_.length==4:
                            sb_=bitstring.BitArray(4)+sb_

                        sb_.reverse()
                        sb.append(sb_)


                    for i in range(sb.length):
                        for di in diList:
                            if di.diaddr == i:
                                di.state = sb[i]
                                di.stateInt = int(sb.bin[i])
                                di.dumpMqtt()
                                self.diMask[str(di.topicIn)][1] = sb[i]

                elif fl == 3:
                    i = res[0]
                    for di in diList:
                        if di.diaddr == i:
                            di.state = bool(res[1])
                            di.stateInt = res[1]
                            di.dumpMqtt()

                elif fl == 5:
                    i = res[0]
                    for di in diList:
                        if di.diaddr == i:
                            di.state = bool(res[1])
                            di.stateInt = res[1]
                            self.diMask[str(di.topicIn)][1] = bool(res[1])
                            di.dumpMqtt()
                            blackOut.work()
            ev.clear()




    def workDIData(self, data):
        dataList = list(data)
        fl=0
        if data[0]== 1:
            #  состояние всех входов
            fl = 1

        elif data[0]==3:
            #  состояние отдельного входа
            fl = 3

        elif data[0]==5:
            fl = 5
            #  событие изменения состояния входа

        return fl, dataList[1:]


    def startDi(self):
        canId = CanId(31, 3)
        byte0 = Byte0(5)

        # byte1 = bitstring.BitArray(6)
        # byte1[5]=part
        # byte1_ = bitstring.BitArray(hex(self.dev['dev']['channel']))[:2]
        # byte1.append(byte1_)
        byte1 = '00'
        data = ''

        dCommand = canId[2:] + canId[:2] + byte0.hex + byte1
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

        self.sock.send_message(dd, size)
        self.answerIs=False

    def reciveData(self, diEvent=None, diQue=None, ):
        device = self.sock
        try:
            out = device.recive_data()
        except BaseException as ex:
            # logging.exception(ex)
            self.mqttc.publish(topic=topic_dump.format(PROJECT) + '/error', payload=str(ex))
        else:
            if out is not None:
                while len(out) > 0:
                    rpgData, rest = self.parceData(out)
                    if hex(rpgData['opCode']) == OPCODECANDATA:
                        self.parceCAN(rpgData['payloadCAN'], diEvent, diQue)
                        # print('===={0}========={1}========'.format(hex(rpgData['payloadCAN']['canId'][0]), hex(rpgData['payloadCAN']['canId'][1])))
                    elif hex(rpgData['opCode']) == OPCODEPINGREQ:
                        print("04 00 00 00")
                    elif hex(rpgData['opCode']) == OPCODECONNECT:
                        print("RPG GATEWAY IS CONNECTED")
                    if len(rest) == 0:
                        break
                    out = out[(len(out) - len(rest)):]


    def listen_rpg1(self, diQue, startEvent, diEvent):

        # device = self.sock

        while True:
            startEvent.wait()
            self.reciveData(diEvent, diQue)



    def parceCAN(self, data, diEvent=None, diq=None):
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
            elif n==5 and diEvent is not None and diq is not None:
                # DI
                diEvent.set()
                diq.put_nowait(data['data'])



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
                    'data': bytearray()
                }
            }
            data['opCode']=dataAr.pop(0)
            for i in range(3):
                data['payloadLen'][i]= dataAr.pop(0)

            for i in range(2):
                data['payloadCAN']['canId'][i]= dataAr.pop(0)

            data['payloadCAN']['dlc'] = data['payloadLen'][0]-2

            for i in range(int(data['payloadLen'][0])-2):
                # data['payloadCAN']['data'][i]=dataAr.pop(0)
                data['payloadCAN']['data'].append(dataAr.pop(0))

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

    def modbusQuery(self, startEvent):
        while True:
            startEvent.wait()
            for prov in self.modbusProviders:
                if (current_milli_time() - prov.getCallTime)>= prov.time_gap:
                    prov.callModBus()

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
                    device.send_message(data, size)
                    # print(data)
                except BaseException as ex:
                    logging.exception(ex)
                    self.mqttc.publish(topic=topic_dump.format(PROJECT) + '/error', payload=str(ex))
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
