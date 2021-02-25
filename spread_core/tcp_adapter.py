import socket
import time
from threading import Timer

from spread_core.tools import settings
from spread_core.tools.service_launcher import Launcher
from spread_core.tools.settings import config, logging

settings.DUMPED = False
BUS_ID = config['BUS_ID']
HOST = config['BUS_HOST']
PORT = config['BUS_PORT']
TIMEOUT = config['BUS_TIMEOUT']
KILL_TIMEOUT = config['KILL_TIMEOUT']

topic_dump = 'Bus/Dump/Mercury/{}'
topic_send = 'Bus/Send/Mercury/{}'
is_lock = False


class TcpSocket:
    def __init__(self):
        self.sock = None
        self._killer = None

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
        out = b''
        self.sock.send(data)
        logging.debug('[->  ]: {}'.format(' '.join(hex(b)[2:].rjust(2, '0') for b in data)))
        while len(out) < r_size:
            out += self.sock.recv(r_size - len(out))
        return out


class TCPAdapterLauncher(Launcher):
    _dumped = False

    def __init__(self):
        self._manager = self
        self.sock = TcpSocket()
        super(TCPAdapterLauncher, self).__init__()

    def start(self):
        self.mqttc.subscribe(topic_send.format(BUS_ID))
        logging.debug('Subscribed to {}'.format(topic_send.format(BUS_ID)))

    def on_message(self, mosq, obj, msg):
        global is_lock
        while is_lock:
            time.sleep(0.3)
        is_lock = True
        data, flags = msg.payload.decode().split('#')
        data = bytes.fromhex(data)
        flags = flags.split(':')
        size = 0
        for flag in flags:
            if 'RS' in flag:
                size = int(flag[2:])
        try:
            out = self.sock.send_message(data, size)
        except BaseException as ex:
            logging.exception(ex)
            self.mqttc.publish(topic=topic_dump.format(BUS_ID) + '/error', payload=str(ex))
        else:
            try:
                out = ''.join(hex(b)[2:].rjust(2, '0') for b in out)
                self.mqttc.publish(topic=topic_dump.format(BUS_ID), payload=out)
                logging.debug('[  <-]: {}'.format(out))
            except BaseException as ex:
                logging.exception(ex)
        finally:
            is_lock = False
            self.sock.start_timer()


def run():
    TCPAdapterLauncher()


if __name__ == '__main__':
    TCPAdapterLauncher()
