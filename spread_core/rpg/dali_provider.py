
from spread_core.mqtt.variables import VariableTRS3
from spread_core.rpg.protocol import *
from spread_core.rpg.settings import *


class DaliProvider:
    def __init__(self, rpgClient, mqtt, *args):
        self._socket = rpgClient
        self.dev = args[0]
        self.mqtt = mqtt
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

    def setLevel(self, level):
        # set level on dali device
        level_=int(level/100*254)
        data = ShortDaliAddtessComm(self.dadr, level_)
        self._call = data

        addr_from = bitstring.BitArray(hex(31))[3:]
        addr_to_ = bitstring.BitArray(hex(self.dev['bus']))
        addr_to = bitstring.BitArray(5 - addr_to_.length)
        addr_to.append(addr_to_)
        addr_from.append(addr_to)
        can_id = bitstring.BitArray(12 - addr_from.length)
        can_id.append(addr_from)
        canId = make_bytes(can_id.hex)

        byte0 = bitstring.BitArray(1)
        echo = bitstring.BitArray(1)
        reserve = bitstring.BitArray(1)
        cls = bitstring.BitArray(5)
        cls[4] = True
        byte0.append(echo)
        byte0.append(reserve)
        byte0.append(cls)

        byte1 = bitstring.BitArray(8)


        byte2 = bitstring.BitArray(8)
        byte2[7 - self.dev['channel']] = True

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
        self._socket.send_message(dd, size)
        # self.answerIs=False
        # return self._callDTime

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
        self._socket.send_message(dd, size)
        self.answerIs=False
        return self._callDTime

    def dumpMqtt(self, data=None, fl=None):
        if data == None and self.state is not None:
            data_ = self.state
            data = data_.uint
        if fl == None:
            comm = 4
            clientTopic = self._stateTopicLevel
        elif fl == 1:
            comm = 2
            clientTopic = self._stateTopicIsOn
            if data == 0:
                data = False
            else:
                data = True

        out = VariableTRS3(None, self.dev['id'], comm, data)
        self.mqtt.publish(topic=clientTopic, payload=out.pack(), qos=0, retain=True)

