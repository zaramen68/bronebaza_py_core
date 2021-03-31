from spread_core.mqtt.variables import VariableTRS3
from spread_core.rpg.protocol import *
from spread_core.rpg.settings import *


class DiProvider:
    def __init__(self, rpgClient, mqtt, *args):
        self._socket = rpgClient
        self.dev = args[0]
        self._mqtt = mqtt
        self._callMTime = 0
        self.state = None
        self.stateInt = 0
        self.lastState = None
        self.lastStateInt = 0
        self.isValid = None
        self.oneByteAnswer = None
        self.twoByteAnswer = None
        self.typeOfQuery = None # 0 - no answer, 1 - need answer
        self.bus = args[0]['dev']['bus']
        self.classF = args[0]['type']
        self.time_gap = args[0]['t_gap']
        self._call = None
        self.answerIs = False
        self.diaddr = args[0]['dev']['diaddr']
        self.topicV = args[0]['dev']['topicV']
        self.type = args[0]['dev']['type']
        self.topicIn = args[0]['dev']['id']

        self._stateTopicLevel = 'Tros3/State/{}/{}'.format(PROJECT, args[0]['dev']['id'])
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

    def getAnswer(self, data):
        print('modbus answer is {}'.format(str(data)))
        self.answerIs = True
        pass

    def askLevel(self):
        pass


    def work(self):
        if abs(self.stateInt-self.lastStateInt)/self.stateInt*100. >= self.dev['pres']:
            self.lastState = self.state
            self.lastStateInt = self.stateInt
            self.dumpMqtt()


    def callDi(self, data = None, part=False):

        self._call = data
        canId = CanId(31, self.dev['dev']['bus'])
        byte0 = Byte0(5)

        byte1 = bitstring.BitArray(6)
        byte1[5]=part
        byte1_ = bitstring.BitArray(hex(self.dev['dev']['channel']))[:2]
        byte1.append(byte1_)

        data_id = make_two_bit(hex(self.dev['dev']['maddr']).split('x')[1])
        data_command = make_two_bit(self.dev['attrib']['command'].split('x')[1])
        data_reg = make_bytes(hex(self.dev['attrib']['reg']).split('x')[1])
        data_nreg = make_bytes(hex(self.dev['attrib']['nreg']).split('x')[1])

        if data is None:
            data = data_id + data_command + data_reg + data_nreg

        dCommand = canId[2:] + canId[:2] + byte0.hex + byte1.hex
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

        self._socket.send_message(dd, size)
        self.answerIs=False
        self._callMTime = current_milli_time()

    def dumpMqtt(self, data=None):
        if data == None:
            data = self.state


        clientTopic = self._stateTopicLevel
        num = 0
        for key, value in self.topicV.items():
            if key == 'isOpenedId':
                out = VariableTRS3(None, self.dev['dev']['id'], num, data)
                self._mqtt.publish(topic=clientTopic+'/{}'.format(num), payload=out.pack(), qos=0, retain=True)
            else:
                out = VariableTRS3(None, self.dev['dev']['id'], num, value)
                self._mqtt.publish(topic=clientTopic+'/{}'.format(num), payload=out.pack(), qos=0, retain=True)
            num += 1

