import socket
import select
import threading
import time
from threading import Timer

from spread_core.mqtt.variables import VariableTRS3
from spread_core.tools import settings
from spread_core.tools.service_launcher import Launcher
from spread_core.tools.settings import config, logging

settings.DUMPED = False
PROJECT=config['PROJ']
BUS_ID=config['BUS_ID']

HOSTnPORT = config['BUS_HOST_PORT']
RPG_HOST = '10.10.1.61'
RPG_PORT = 55577
TIMEOUT = config['BUS_TIMEOUT']
KILL_TIMEOUT = config['KILL_TIMEOUT']


# topic_dump = 'Tros3/State/{}/{}/{}'
# topic_send = 'ModBus/from_Client/{}'
topic_send =config['TOPIC_SEND']
topic_dump = config['TOPIC_DUMP']

is_lock=False


class RGPTcpSocket:

    def __init__(self, host, port):

        self._killer = None
        self._port=port
        self._host=host
#        self.devices=kwargs
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
        logging.debug('[->  ]: {}'.format(' '.join(hex(b)[2:].rjust(2, '0').upper() for b in data)))
       # while len(out) < r_size:
       #     out += self.sock.recv(1024)
       #if len(out) > r_size:
       #     out = out[out.rindex(data[0]):]
        out=self.sock.recv(256)
        logging.debug('[  <-]: {}'.format(' '.join(hex(b)[2:].rjust(2, '0').upper() for b in out)))
        out_str='{}'.format(''.join(hex(b)[2:].rjust(2, '0').upper() for b in out))
        return out_str

    def recive_data(self):
        self.stop_timer()
        if self.sock is None:
            self.create()
        try:
            out = self.sock.recv(256)
        except  BaseException as ex:
            logging.exception(ex)
            return None
        else:
            logging.debug('[  <-]: {}'.format(' '.join(hex(b)[2:].rjust(2, '0').upper() for b in out)))
            out_str = '{}'.format(''.join(hex(b)[2:].rjust(2, '0').upper() for b in out))
            return out_str

    # def commands(self):
    #     return self._commands


class RGPTCPAdapterLauncher(Launcher):
    _dumped = False
    _command_event = threading.Event()

    def __init__(self):
        self._manager = self
        self._stopped = False
        self.sock= RGPTcpSocket(RPG_HOST, RPG_PORT)
        self._start_time = time.time()
        super(RGPTCPAdapterLauncher, self).__init__()


    def start(self):
        self._command_event.set()
        self.connect_rpg()
        self.rpg_listen_fun()
        listen = threading.Thread(target=self.listen_rpg)
        listen1 = threading.Thread(target=self.listen_rpg1)

        # for topic in topic_send:
        #     self.mqttc.subscribe(topic)
        #     logging.debug('Subscribed to {}'.format(topic))
        for topic in topic_dump:
            self.mqttc.subscribe(topic)
            logging.debug('Subscribed to {}'.format(topic))

        listen.start()
        listen1.start()


    def on_message(self, mosq, obj, msg):

        self._command_event.clear()
        self._stopped = True
        global is_lock
        while is_lock:
            time.sleep(0.3)
        is_lock = True
        host, port, data, flags = msg.payload.decode().split('#')

        data = bytes.fromhex(data)
        flags = flags.split(':')
        size = 0
        for flag in flags:
            if 'RS' in flag:
                size = int(flag[2:])
        device = self.sock
        if device._port == int(port) and device._host==host:

            try:
                pass
                #device.send_message(data, size)
                #out=data
                #print(data)
            except BaseException as ex:
                logging.exception(ex)
                # self.mqttc.publish(topic=topic_dump.format(PROJECT, BUS_ID, '0') + '/error', payload=str(ex))
            else:
                try:
                    out = ''.join(hex(b)[2:].rjust(2, '0') for b in data)
                    self.mqttc.publish(topic=topic_dump.format(PROJECT, BUS_ID, '0'), payload=out)
                    logging.debug('[  <-]: {}'.format(out))
                except BaseException as ex:
                    logging.exception(ex)
            finally:
                is_lock = False
                #device.start_timer()

        self._stopped = False
        self._command_event.set()
       # self.mqttc.subscribe(topic_send.format(BUS_ID))
        #self.mqttc.loop_start()



    def rpg_listen_fun(self):

        data = '07050000E103824200' #запрос настроек канала 00
        # data = '07080000E103824000040000' #установка скорости 19200 на 00 канале
        size = len(data)
        data = bytes.fromhex(data)
        device = self.sock

        try:
            out = device.send_message(data, size)
            print('запрос на состояние модуля 1 ModBus: {0}'.format(data))
            print('ответ: {0}'.format(out))
        except BaseException as ex:
            logging.exception(ex)
            self.mqttc.publish(topic=topic_dump.format(BUS_ID) + '/error', payload=str(ex))
        else:
            try:
                self._start_time = time.time()
            # out = VariableTRS3(None, int(BUS_ID), 0, tk)
            # top_out = topic_dump.format(PROJECT, BUS_ID, '0')
            # self.mqttc.publish(topic=topic_dump.format(PROJECT, BUS_ID, '0'), payload=out.pack())
                logging.debug('[  <-]: {}'.format(out))

            except BaseException as ex:
                logging.exception(ex)

    def listen_rpg1(self):

        inputs = [self.sock]
        outputs = []
        messages = {}

        while True:
            reads, send,  excepts = select.select(inputs, outputs, inputs)
            for conn in reads:

                if conn == self.sock:
                    try:

                            out = self.sock.recive_data()
                            # if out:
                            #     break
                            #

                    except BaseException as ex:
                        logging.exception(ex)
                        # self.mqttc.publish(topic=topic_dump.format(BUS_ID) + '/error', payload=str(ex))
                    else:
                        try:
                            logging.debug('[recive from server  <-]: {}'.format(out))

                        except BaseException as ex:
                            logging.exception(ex)



    def write_to_bro(self, topId, num, value):
        out = VariableTRS3(None, topId, num, value)
        self.mqttc.publish(topic=topic_dump.format(PROJECT, str(topId), str(num)), payload=out.pack())
        logging.debug('[  <-]: {}'.format(out))

    def listen_rpg(self):
        while True:
            # time.sleep(1)    10 03 01 02 00 02 - команда чтения температуры
            # self._command_event.wait()


            if (time.time()- self._start_time) >= 5.:
                device = self.sock
                # for data in device.commands():
                data = '07 0A 00 00 E1 03 02 00 10 03 01 02 00 02'
                size = len(data.strip())
                data = bytes.fromhex(data.strip())
                try:
                    out = device.send_message(data, size)
                    print(data)
                    print(out)
                    print('time is {0}, start time is {1}'.format(time.time(), self._start_time))
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

                # for data in device.commands():
                data = '03000000'
                size=len(data)
                data = bytes.fromhex(data)
                try:
                    out = device.send_message(data, size)
                    print(data)
                except BaseException as ex:
                    logging.exception(ex)
                    # self.mqttc.publish(topic=topic_dump.format(BUS_ID) + '/error', payload=str(ex))
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
    RGPTCPAdapterLauncher()




if __name__ == '__main__':
    run()
    # TCPAdapterLauncher()
