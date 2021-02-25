import json
import random
import socket
import threading
import time
from threading import Timer

from spread_core.mqtt import of, TopicProject, TopicCommandTros3, TopicState, TopicCommand
from spread_core.mqtt.variables import VariableTRS3, VariableReader, VariableJocket
from spread_core.tools import settings
from spread_core.tools.service_launcher import Launcher
from spread_core.tools.settings import config, logging

settings.DUMPED = False

HOST = '10.10.1.145'
PORT = 502

TIMEOUT = 3
KILL_TIMEOUT = 3


class ModbusTcpSocket:

    def __init__(self, host, port):

        self._killer = None
        self._port=port
        self._host=host
        self.sock=None
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
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




class ModBusTCPAdapterLauncher(Launcher):
    _dumped = False
    _command_event = threading.Event()

    def __init__(self):
        self._manager = self
        self._stopped = False
        #self.sock=ModbusTcpSocket(HOST, PORT)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # while True:
        #     try:
        #         self.create()
        #     except ConnectionRefusedError as ex:
        #         logging.exception(ex)
        #         time.sleep(3)
        #     else:
        #         break

        # super(ModBusTCPAdapterLauncher, self).__init__()
        self.listen_all()

    def create(self):
        logging.debug('Create socket')
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(TIMEOUT)
        while True:
            try:
                self.sock.connect((HOST, PORT))
            except ConnectionRefusedError as ex:
                logging.exception(ex)
                time.sleep(3)
            else:
                break

    def send_message(self, data, r_size):
        # self.stop_timer()
        if self.sock is None:
            self.create()
        self.sock.send(data)
        logging.debug('[->  ]: {}'.format(' '.join(hex(b)[2:].rjust(2, '0').upper() for b in data)))
        out=self.sock.recv(2048)
        logging.debug('[  <-]: {}'.format(' '.join(hex(b)[2:].rjust(2, '0').upper() for b in out)))
        out_str='{}'.format(''.join(hex(b)[2:].rjust(2, '0').upper() for b in out))
        return out_str

    def listen_all(self):
        while True:
            time.sleep(1)
#                                             Опрос tcp устройств

            transaction_id = hex(random.getrandbits(10)).split('x')[1]
            transaction_id = make_bytes(transaction_id)
            data = transaction_id + \
                   '00000006' + \
                   make_two_bit(hex(2).split('x')[1]) + \
                   '0x05'.split('x')[1] + \
                   '3c00' + 'FF00'

            size = len(data)
            data = bytes.fromhex(data)
            try:
                self.create()
                out = self.send_message(data, size)
            except BaseException as ex:
                logging.exception(ex)
            else:
                result = str(out)





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
