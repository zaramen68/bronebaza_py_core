import socket
import select
import threading
import time
from tornado import gen, iostream
from tornado.tcpclient import TCPClient
from tornado.ioloop import IOLoop
from tornado.ioloop import PeriodicCallback
import time
import struct
import  random

from tornado import gen
from tornado.ioloop import IOLoop
from tornado.iostream import IOStream, StreamClosedError
from tornado.tcpclient import TCPClient
from tornado.tcpserver import TCPServer
from tornado.platform.asyncio import to_tornado_future, to_asyncio_future
from threading import Timer

from spread_core.mqtt.variables import VariableTRS3
from spread_core.tools import settings
from spread_core.tools.service_launcher import Launcher
from spread_core.tools.settings import config, logging

HEARTBEAT_TIMEOUT = 5
DALI_ASK_TIME = 20

settings.DUMPED = False
PROJECT=config['PROJ']
BUS_ID=config['BUS_ID']

HOSTnPORT = config['BUS_HOST_PORT']
RPG_HOST = '10.10.1.69'
RPG_PORT = 55577
TIMEOUT = config['BUS_TIMEOUT']
KILL_TIMEOUT = config['KILL_TIMEOUT']


# topic_dump = 'Tros3/State/{}/{}/{}'
# topic_send = 'ModBus/from_Client/{}'
topic_send =config['TOPIC_SEND']
topic_dump = config['TOPIC_DUMP']

is_lock=False

def get_utc():
    return int(time.time())

class TCP_Client(object):


    def __init__(self, host, port):
        # self.ioloop = ioloop
        self.recv_cb =  lambda : True
        self.host = host
        self.port = port

        self.last_heartbeat_time = 0
        self.cnt = 0

        self.seq = 1
        self.login_aes_key = b''
        self.recv_data = b''
        self.heartbeat_callback = None
        self.flag = 1
        self.dali_id =0

    @gen.coroutine
    def start(self):
        wait_sec = 1
        while True:
            try:
                self.stream = yield TCPClient().connect(self.host, self.port)
                break
            except iostream.StreamClosedError:
                logging.error("connect error and again")
                yield gen.sleep(wait_sec)
                wait_sec = (wait_sec if (wait_sec >= 60) else (wait_sec * 2))

        self.link_to_gateway()



        # self.stream.read_bytes(16, self.__recv_header)


        # self.read_data()

        # self.send_heart_beat()
        #
        # self.read_data_callback = PeriodicCallback(self.read_data, 10 * HEARTBEAT_TIMEOUT)
        # self.read_data_callback.start()
        #
        # time.sleep(1)
        #
        # self.heartbeat_callback = PeriodicCallback(self.send_heart_beat, 1000 * HEARTBEAT_TIMEOUT)
        # self.heartbeat_callback.start()  # start scheduler

        # self.test_dali_num()
        # self.test_dali_callback = PeriodicCallback(self.test_dali_num, 100 * DALI_ASK_TIME)
        # self.test_dali_callback.start()

        # self.send_dali_callback = PeriodicCallback(self.send_dali, 100 * DALI_ASK_TIME)
        # self.send_dali_callback.start()

        # io_loop = tornado.ioloop.IOLoop.current()
        # io_loop.run_sync(self.test_dali_num)


        print('the end')

    @gen.coroutine
    def restart(self, host, port):
        if self.heartbeat_callback:
            #
            self.heartbeat_callback.stop()
        if self.read_data_callback:
            self.read_data_callback.stop()
        self.host = host
        self.port = port
        self.stream.set_close_callback(self.__closed)
        yield self.stream.close()

    def __closed(self):
        self.start()

    @gen.coroutine
    def read_data(self):
        if not self.stream.reading():
            try:
                out = yield self.stream.read_bytes(64, partial=True)
            except iostream.StreamClosedError:
                logging.error("stream read error, TCP disconnect and restart")
                self.restart(self.host, self.port)
            else:
                # l_out = str(out)[2:-1].split('_')
                # for t_out in l_out:
                #     print (t_out)
                print(out.hex())
        else:
            # print('stream is beezy')
            pass

    def send_heart_beat(self):
        # logging.debug('last_heartbeat_time = {}, elapsed_time = {}'.format(self.last_heartbeat_time,
        #                                                                   get_utc() - self.last_heartbeat_time))

        if (get_utc() - self.last_heartbeat_time) >= HEARTBEAT_TIMEOUT:
            data = '03000000'
            # send_data = self.pack(CMDID_NOOP_REQ)
            send_data = self.my_pack(data)
            self.send(send_data)

            self.last_heartbeat_time = get_utc()
            return True
        else:
            return False





    def link_to_gateway(self):
        data = '0104000001001027'
        send_data = self.my_pack(data)
        try:
            self.send(send_data)
        except:
            print("gateway is not able")




    def send(self, data):
        try:
            self.stream.write(data)
        except iostream.StreamClosedError:
            logging.error("stream write error, TCP disconnect and restart")
            self.restart(self.host, self.port)

    def stop(self):
        self.ioloop.stop()




    def my_pack(self, data):
        b_data = bytes.fromhex(data.strip())
        return b_data
    #

class RGPTCPAdapterLauncher(Launcher):
    _dumped = False
    _command_event = threading.Event()

    def __init__(self):
        self._manager = self
        self._stopped = False
        self.sock= TCP_Client(RPG_HOST, RPG_PORT)

        self._start_time = time.time()
        self._last_time = time.time()
        super(RGPTCPAdapterLauncher, self).__init__()


    def start(self):

        ioloop = IOLoop.instance()

        self.sock.start()
        ioloop.start()

        # self._command_event.set()
        # self.connect_rpg()
        # self.rpg_listen_fun()
        # listen = threading.Thread(target=self.listen_rpg)
        # listen1 = threading.Thread(target=self.listen_rpg1)

        # for topic in topic_send:
        #     self.mqttc.subscribe(topic)
        #     logging.debug('Subscribed to {}'.format(topic))
        for topic in topic_dump:
            self.mqttc.subscribe(topic)
            logging.debug('Subscribed to {}'.format(topic))

        # listen.start()
        # listen1.start()
        yield  self.listen_rpg1()
        self.test_dali_num()


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

    def test_dali_num(self):
        for i in range(0, 10):
            time.sleep(1)
            print('id={0}'.format(i))

            ii = hex(int((bin(i) + '1'), 2))
            ii = ii[2:]
            if len(ii) == 1:
                ii = '0' + ii
            print('ii={0}'.format(ii))

            data = '07 07 00 00 E2 03 01 04 01 {0} A0'.format(ii)
            # data = '07 07 00 00 E2 03 01 00 01 FE 00'
            send_data = self.sock.my_pack(data)

            yield self.sock.send(send_data)



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
            self.mqttc.publish(topic=topic_dump[2].format(BUS_ID) + '/error', payload=str(ex))
        else:
            try:
                data = '07080000E103824000040000' #установка скорости 19200 на 00 канале
                size = len(data)
                data = bytes.fromhex(data)
                device = self.sock
                try:
                    out1 = device.send_message(data, size)
                    print('settings 19200 b на модуля 1 ModBus: {0}'.format(data))
                    print('ответ: {0}'.format(out1))
                except BaseException as ex:
                    logging.exception(ex)
                    self.mqttc.publish(topic=topic_dump[2].format(BUS_ID) + '/error', payload=str(ex))
                else:
                    self._start_time = time.time()

            # out = VariableTRS3(None, int(BUS_ID), 0, tk)
            # top_out = topic_dump.format(PROJECT, BUS_ID, '0')
            # self.mqttc.publish(topic=topic_dump.format(PROJECT, BUS_ID, '0'), payload=out.pack())
                logging.debug('[  <-]: {}'.format(out))

            except BaseException as ex:
                logging.exception(ex)

    def listen_rpg1(self):


        while True:

            try:

                out = yield self.sock.read_data()


            except BaseException as ex:
                logging.exception(ex)
                #
            else:
                if out is not None:
                    print(out)
                    self.mqttc.publish(topic=topic_send[2] + '/tmp', payload=str(out))
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

                delta_time = time.time()-self._last_time

                data = '03000000'
                size = len(data)
                data = bytes.fromhex(data)
                try:
                    print('delt time is {0}'.format(delta_time))
                    out = device.send_message(data, size)
                    print('состояние связи со шлюзом = {0}'.format(out))

                except BaseException as ex:
                    logging.exception(ex)
                    # self.mqttc.publish(topic=topic_dump.format(BUS_ID) + '/error', payload=str(ex))
                else:

                    self._start_time = time.time()
                    if out == '04000000':
                        print('^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^')

                self._last_time = time.time()

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
