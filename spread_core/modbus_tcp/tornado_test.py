import tornado
from tornado import gen, iostream
from tornado.tcpclient import TCPClient
from tornado.ioloop import IOLoop
from tornado.ioloop import PeriodicCallback
import time
import struct
import  random

from spread_core.tools.settings import config, logging

# recv缓冲区大小
BUFFSIZE = 4096

# 心跳包seq id
HEARTBEAT_SEQ = 0xFFFFFFFF


IDENTIFY_SEQ = 0xFFFFFFFE


PUSH_SEQ = 0

# cmd id
CMDID_NOOP_REQ = 6  # 心跳
CMDID_IDENTIFY_REQ = 205  # 长链接确认
CMDID_MANUALAUTH_REQ = 253  # 登录
CMDID_PUSH_ACK = 24  # 推送通知
CMDID_REPORT_KV_REQ = 1000000190  # 通知服务器消息已接收

# 解包结果
UNPACK_NEED_RESTART = -2  # 需要切换DNS重新登陆
UNPACK_FAIL = -1  # 解包失败
UNPACK_CONTINUE = 0  # 封包不完整,继续接收数据
UNPACK_OK = 1  # 解包成功


HOST='10.10.1.69'
PORT = 55577
RETRY_TIMES = 3

def recv_data_handler(recive_data):
    # logging.debug("tornado recv: ", recv_data)
    pass



# 心跳时间间隔（秒）
HEARTBEAT_TIMEOUT = 5
DALI_ASK_TIME = 20

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


        self.read_data()

        self.send_heart_beat()

        self.read_data_callback = PeriodicCallback(self.read_data, 10 * HEARTBEAT_TIMEOUT)
        self.read_data_callback.start()

        time.sleep(1)

        self.heartbeat_callback = PeriodicCallback(self.send_heart_beat, 1000 * HEARTBEAT_TIMEOUT)
        self.heartbeat_callback.start()  # start scheduler

        # self.test_dali_num()
        self.test_dali_callback = PeriodicCallback(self.test_dali_num, 100 * DALI_ASK_TIME)
        self.test_dali_callback.start()

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
                self.restart(HOST, PORT)
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

    @gen.coroutine
    def send_dali(self):

        # logging.debug('sending dali command: last_heartbeat_time = {}, elapsed_time = {}'.format(self.last_heartbeat_time,
        #                                                                    get_utc() - self.last_heartbeat_time))
        if self.dali_id == 0:

            self.flag = 1
        if self.dali_id >= 10:
            self.flag = -1

        if self.flag > 0:

            fe = random.randint(0, 255)
            fex = hex(fe)[2:]

            if len(fex) == 1:
                fex='0'+fex

            ii = hex(int((bin(self.dali_id) + '0'), 2))
            ii = ii[2:]
            if len(ii)==1:
                ii = '0'+ ii
            self.dali_id = self.dali_id + 1

            data = '07 07 00 00 E2 03 01 00 01 {0} {1}'.format(ii, fex)
            # data = '07 04 00 00 E2 03 81 00'
            print('send command {0}'.format(data))

            send_data = self.my_pack(data)

            self.send(send_data)
            # logging.debug(
            #     'sending dali command: last_heartbeat_time = {}, elapsed_time = {}'.format(self.last_heartbeat_time,
            #                                                                                get_utc() - self.last_heartbeat_time))
            # self.last_heartbeat_time = get_utc()

        else:


            ii = hex(int((bin(self.dali_id) + '0'), 2))
            ii = ii[2:]
            if len(ii)==1:
                ii = '0'+ ii
            self.dali_id = self.dali_id - 1
            data = '07 07 00 00 E2 03 01 00 01 {0} 00'.format(ii)
            # data = '07 07 00 00 E2 03 01 00 01 FE 00'
            send_data = self.my_pack(data)

            self.send(send_data)

            # self.last_heartbeat_time = get_utc()
            #
            # logging.debug(
            #     'sending dali command: last_heartbeat_time = {}, elapsed_time = {}'.format(self.last_heartbeat_time,
            #                                                                                get_utc() - self.last_heartbeat_time))

        return True

    @gen.coroutine
    def test_dali_num(self):
        # for i in range(0, 10):
        #     time.sleep(1)

            i=self.dali_id
            ii = hex(int((bin(i) + '1'), 2))
            ii = ii[2:]
            if len(ii) == 1:
                ii = '0' + ii

            data = '07 07 00 00 E1 03 01 04 01 {0} A0'.format(ii)
            # data = '07 07 00 00 E2 03 01 00 01 FE 00'
            send_data = self.my_pack(data)

            yield self.send(send_data)
            self.dali_id = self.dali_id+1


    def link_to_gateway(self):
        data = '0104000001001027'
        send_data = self.my_pack(data)
        try:
            self.send(send_data)
        except:
            print("gateway is not able")


    @gen.coroutine
    def __recv_header(self, data):
        self.cnt += 1
        self.recv_data = data
        logging.debug('recive from the server', data)
        (len_ack, _, _) = struct.unpack('>I4xII', data)
        if self.recv_cb:
            self.recv_cb(data)
        try:
            yield self.stream.read_bytes(len_ack - 16, self.__recv_payload)
        except iostream.StreamClosedError:
            logging.error("stream read error, TCP disconnect and restart")
            self.restart(HOST, PORT)

    @gen.coroutine
    def __recv_payload(self, data):
        logging.debug('recive from the server', data)
        if self.recv_cb:
            self.recv_cb(data)
        self.recv_data += data
        if data != b'':
            (ret, buf) = self.unpack(self.recv_data)
            if UNPACK_OK == ret:
                while UNPACK_OK == ret:
                    (ret, buf) = self.unpack(buf)
                # 刷新心跳
                self.send_heart_beat()
            if UNPACK_NEED_RESTART == ret:  # 需要切换DNS重新登陆
                if RETRY_TIMES > 0:
                    self.restart(HOST, PORT)
                    return
                else:
                    logging.error('............')
                    self.stop()
        try:
            yield self.stream.read_bytes(16, self.__recv_header)
        except iostream.StreamClosedError:
            logging.error("stream read error, TCP disconnect and restart")
            self.restart(HOST, PORT)

    def send(self, data):
        try:
            self.stream.write(data)
        except iostream.StreamClosedError:
            logging.error("stream write error, TCP disconnect and restart")
            self.restart(HOST, PORT)

    def stop(self):
        self.ioloop.stop()


    def pack(self, cmd_id, buf=b''):
        header = bytearray(0)
        header += struct.pack(">I", len(buf) + 16)
        header += b'\x00\x10'
        header += b'\x00\x01'
        header += struct.pack(">I", cmd_id)
        if CMDID_NOOP_REQ == cmd_id:  # 心跳包
            header += struct.pack(">I", HEARTBEAT_SEQ)
        elif CMDID_IDENTIFY_REQ == cmd_id:
            header += struct.pack(
                ">I", IDENTIFY_SEQ
            )
            # Пакет подтверждения входа в систему (еще не реализован;
            # после успешного подтверждения запроса сервер будет непосредственно выталкивать содержимое сообщения,
            # в противном случае сервер отправляет только push-уведомление,вам нужно взять на себя инициативу по синхронизации сообщения
        else:
            header += struct.pack(">I", self.seq)
            #
            self.seq += 1

        return header + buf

    def my_pack(self, data):
        b_data = bytes.fromhex(data.replace(' ', ''))
        return b_data
    #
    def unpack(self, buf):
        if len(buf) < 16:
            return (UNPACK_CONTINUE, b'')
        else:
            #
            header = buf[:16]
            (len_ack, cmd_id_ack, seq_id_ack) = struct.unpack('>I4xII', header)
            logging.debug('Длина пакета:{},cmd_id:{},seq_id:0x{:x}'.format(len_ack, cmd_id_ack,
                                                                  seq_id_ack))

            if len(buf) < len_ack:
                return (UNPACK_CONTINUE, b'')
            else:

                return (UNPACK_OK, buf[len_ack:])

        return (UNPACK_OK, b'')


def run():

    ioloop = IOLoop.instance()
    tcp_client = TCP_Client(host = HOST, port = PORT)
    tcp_client.start()
    ioloop.start()






if __name__ == '__main__':
    run()