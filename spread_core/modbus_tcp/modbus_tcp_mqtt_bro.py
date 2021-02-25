import json
import random
import socket
import threading
import time
from threading import Timer


from spread_core.mqtt.variables import VariableTRS3
from spread_core.tools import settings
from spread_core.tools.service_launcher import Launcher
from spread_core.tools.settings import config, logging

settings.DUMPED = False
PROJECT = config['PROJECT_ID']
BROKER_HOST = config['BROKER_HOST']
BROKER_PORT = config['BROKER_PORT']
BROKER_USERNAME = config['BROKER_USERNAME']
BROKER_PWD = config['BROKER_PASSWORD']

TIMEOUT = config['BUS_TIMEOUT']
KILL_TIMEOUT = config['KILL_TIMEOUT']

TCP_DEV = dict()

topic_dump = 'ModBus/State/{}/{}/{}/{}/{}'
topic_subs = 'Project/File/{}/tcp_dev.json'

protocol = config['PROTOCOL']


class ModbusTcpSocket:

    def __init__(self, host, port, *args):

        self._killer = None
        self._port=port
        self._host=host
        self.sock=None

        self._things= args

        self.create()



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
        logging.debug('[->  ]: {}'.format(' '.join(hex(b)[2:].rjust(2, '0').upper() for b in data)))
        out=self.sock.recv(2048)
        logging.debug('[  <-]: {}'.format(' '.join(hex(b)[2:].rjust(2, '0').upper() for b in out)))
        out_str='{}'.format(''.join(hex(b)[2:].rjust(2, '0').upper() for b in out))
        return out_str

    def things(self):
        return self._things


class ModBusTCPAdapterLauncher(Launcher):
    _dumped = False
    _command_event = threading.Event()

    def __init__(self):
        self._manager = self
        self._stopped = False
        self.sock=[]
        self.sock_night = None
        self.mqttc.on_subscribe = self.on_subscribe
        self.mqttc.on_connect = self.on_connect
        self.mqttc.on_message = self.on_message
        self.mqttc.connect(BROKER_HOST, BROKER_PORT)
        self.mqttc.subscribe(topic=topic_subs.format(PROJECT), qos=1)

        self.start()


    def start(self):
        self._command_event.set()
        listen = threading.Thread(target=self.listen_all)
        listen.start()
        self.mqttc.loop_forever()

    def on_connect(self, mqttc, userdata, flags, rc):
        if rc==0:
            print("connected OK Returned code=",rc)
        else:
            print("Bad connection Returned code=",rc)

    def on_subscribe(self, mqttc, userdata, mid, granted_qos):
        print("Subscribed: " + str(mid) + " " + str(granted_qos))

    def on_message(self, mqttc, userdata, msg):

        try:
            dev = msg.payload.decode()
            TCP_DEV = json.loads(dev)
            for dev in TCP_DEV['tcp_dev']:
                self.sock.append(ModbusTcpSocket(dev['host'], dev['port'], dev['dev']))
            self.mqttc.loop_stop()

        except BaseException as ex:
            logging.exception(ex)

    def write_to_bro(self, topId, num, value):
        out = VariableTRS3(None, topId, num, value)
        self.mqttc.publish(topic=topic_dump.format(PROJECT, str(topId), str(num)), payload=out.pack())
        logging.debug('[  <-]: {}'.format(out))

    def listen_all(self):

        while True:
            if len(self.sock) != 0:

#                                             Опрос tcp устройств
                for device in self.sock:
                    things = device.things()
                    for thing in things[0]:
                        transaction_id = hex(random.getrandbits(10)).split('x')[1]
                        transaction_id = make_bytes(transaction_id)
                        data_body = make_two_bit(hex(thing['id']).split('x')[1]) + \
                               thing['cmd'].split('x')[1] + \
                               make_bytes(hex(thing['reg']).split('x')[1]) + make_bytes(hex(thing['nreg']).split('x')[1])

                        data = transaction_id + protocol + make_bytes(str(int(len((data_body))/2))) + data_body


                        size = len(data)
                        data = bytes.fromhex(data)
                        try:
                            out = device.send_message(data, size)
                        except TimeoutError as ex:
                            logging.exception(ex)
                            device.kill()
                            device.create()
                        except OSError as ex:
                            logging.exception(ex)
                            device.kill()
                            device.create()


                        except BaseException as ex:
                            logging.exception(ex)
                        else:
                            result = str(out)
                            if result[:4].lower() == transaction_id:
                                dev_topic = topic_dump.format(PROJECT, device._host, thing['type'], thing['id'], thing['reg'])
                                self.mqttc.publish(topic=dev_topic, payload=str(out), qos=1, retain=True)




def run():
    ModBusTCPAdapterLauncher()

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
