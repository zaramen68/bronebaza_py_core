import json
import random
import socket
import threading
import time

import bitstring
import paho.mqtt.client

from threading import Timer

from spread_core.mqtt import of, TopicProject, TopicCommandTros3, TopicState, TopicCommand
from spread_core.mqtt.variables import VariableTRS3, VariableReader, VariableJocket
from spread_core.tools import settings
from spread_core.tools.service_launcher import Launcher
from spread_core.tools.settings import config, logging

settings.DUMPED = False
PROJECT = config['PROJ']
BUS_ID = config['BUS_ID']
HOST = config['BUS_HOST']
PORT = config['BUS_PORT']
#HOSTnPORT = config['BUS_HOST_PORT']
#NIGHT_HOST_PORT=config['NIGHT_HOST_PORT']
TIMEOUT = config['BUS_TIMEOUT']
KILL_TIMEOUT = config['KILL_TIMEOUT']
#THINGS=config['THINGS']
#NIGHT_THINGS= config['NIGHT_THINGS']
#TOPIC_SUB = config['TOPIC_SUB']
TOPIC_PUB = config['TOPIC_PUB']
MSG_SUB = config['MSG_SUB']
SAVED_DATA = config['SAVED_DATA']
MODBUS_DEV = config['MODBUS_DEV']

ROJECT_ID = config['PROJECT_ID']
BROKER_HOST = config['BROKER_HOST']
BROKER_PORT = config['BROKER_PORT']
BROKER_USERNAME = config['BROKER_USERNAME']
BROKER_PWD = config['BROKER_PASSWORD']

topic_dump = 'ModBus/State/{}/{}/{}/{}/{}'
topic_send = 'ModBus/from_Client/{}'
topic_dali = 'Jocket/Command/{projet_id}/le_sid/Hardware/AppServer/{server_id}/RapidaDali/{}manager_id/RapidaDaliDimmer/{provider_id}/BrightnessLevel'

protocol = config['PROTOCOL']

rpgtopic_send =config['TOPIC_SEND']
rpgtopic_dump = config['TOPIC_DUMP']
# is_night = False
# night_di0 = False
# night_di1 = False
# night_di0_old = False
# night_di1_new = False
# night_reg = 0
# reg_sw = 0

current_milli_time = lambda: int(round(time.time() * 1000))


class ModBusRPGAdapterLauncher(Launcher):
    _dumped = False
    _command_event = threading.Event()

    def __init__(self):

        self._time = current_milli_time()
        # self.mqttc = paho.mqtt.client.Client()
        # self.mqttc.username_pw_set(BROKER_USERNAME, BROKER_PWD)
        # self.mqttc.on_connect = self.on_connect
        # self.mqttc.on_subscribe = self.on_subscribe
        # self.mqttc.on_message = self.on_message
        # self.mqttc.connect(BROKER_HOST, BROKER_PORT)
        # self._manager = self
        # self._stopped = False

        self._start_time = time.time()
        self._manager = self
        self._stopped = False
        self.sock=[]
        self.sock_night = None
        self.msg_sub=MSG_SUB
        self.saved_data = SAVED_DATA
        self.devices = MODBUS_DEV

        # for dev in TCP_DEV:
        #     self..append(ModbusTcpSocket(dev['host'], dev['port'], dev['dev']))
        #

        super(ModBusRPGAdapterLauncher, self).__init__()

    def start(self):
        self._command_event.set()
        listen = threading.Thread(target=self.listen_all)
        listen.start()


    def write_to_bro(self, topId, num, value):
        out = VariableTRS3(None, topId, num, value)
        self.mqttc.publish(topic=topic_dump.format(PROJECT, str(topId), str(num)), payload=out.pack())
        logging.debug('[  <-]: {}'.format(out))

    def listen_all(self):

        while True:
            #time.sleep(1)
#                                             Опрос tcp устройств
            for thing in self.devices:

                can_id=make_can_id(31, thing['module_addr'])
                canId=make_bytes(can_id.hex)

                byte0 = bitstring.BitArray(8)
                byte1 = bitstring.BitArray(8)
                byte0[0]= False
                byte0[6]= True
                channel = bitstring.BitArray(hex(thing['channel']))
                byte1[7]= channel[3]
                byte1[6]= channel[2]

                sbyte0=str(byte0)[2:]


                transaction_id = hex(random.getrandbits(10)).split('x')[1]
                transaction_id = make_bytes(transaction_id)

                data_body = make_two_bit(hex(thing['id']).split('x')[1]) + \
                       thing['cmd'].split('x')[1] + \
                       make_bytes(hex(thing['reg']).split('x')[1]) + make_bytes(hex(thing['nreg']).split('x')[1])

                data = canId[2:]+ canId[:2] + byte0.hex + byte1.hex + make_bytes(str(int(len((data_body))/2))) + data_body


                size = len(data)
                data = bytes.fromhex(data)
                try:
                    self.mqttc.publish(topic=rpgtopic_send[2], payload=data, qos=1, retain=True)



                except BaseException as ex:
                    logging.exception(ex)
                # else:
                #     result = str(out)
                #     if result[:4].lower() == transaction_id:
                #         dev_topic = topic_dump.format(PROJECT, device._host, thing['type'], thing['id'], thing['reg'])
                #         self.mqttc.publish(topic=dev_topic, payload=str(out), qos=1, retain=True)




def run():
    ModBusRPGAdapterLauncher()

def make_can_id(addr_from, addr_to):
    addr_from = bitstring.BitArray(hex(2))
    addr_to = bitstring.BitArray(hex(31))
    can_id = bitstring.BitArray(12)
    delta = can_id.length - addr_to.length
    bravo = can_id.length - addr_from.length
    if addr_to.length < 5:
        for i in range(addr_to.length - 1, 0, -1):
            can_id[i + 8] = addr_to[i]
    else:
        for i in range(addr_to.length - 1, addr_to.length - 6, -1):
            can_id[i + delta] = addr_to[i]
    if addr_from.length < 5:
        for i in range(addr_from.length - 1, 0, -1):
            can_id[bravo - 5 + i] = addr_from[i]
    else:
        for i in range(addr_from.length - 1, addr_from.length - 6, -1):
            can_id[i - 1] = addr_from[i]

    return can_id

def make_bytes(x):
    bytes_list =list('0000')
    list_x = list(x)
    i=-1
    while abs(i) <= len(x):
        bytes_list[i]=list_x[i]
        i=i-1
    return ''.join(bytes_list)

def make_two_bit(x):
    bytes_list =list('00')
    list_x = list(x)
    i=-1
    while abs(i) <= len(x):
        bytes_list[i]=list_x[i]
        i=i-1
    return ''.join(bytes_list)


if __name__ == '__main__':
    run()
    # TCPAdapterLauncher()
