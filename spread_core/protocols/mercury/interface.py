import datetime
import socket
import threading

from spread_core import mqtt
from spread_core.mqtt import TopicTcp
from spread_core.protocols.mercury.commands import OpenSession, CloseSession, CheckConnect
from spread_core.protocols.mercury.errors import TimeOutError, BadConnectResponse

SESSION_TIME = 230
TIMEOUT = 3


class _Interface:
    def __init__(self, p1='', p2='', p3=''):
        self.p1 = p1
        self.p2 = p2
        self.p3 = p3
        self._deprecate_time = 0
        self.has_failed = []

    def check_access(self, address, level):
        ts = datetime.datetime.now().timestamp()
        r = dict(value=False)
        if level == 2:
            r = self._apply(OpenSession(address, 0x2, self.p2))
        elif ts - self._deprecate_time >= SESSION_TIME:
            r = self._apply(OpenSession(address, 0x1, self.p1))
            self._deprecate_time = ts

    def send(self, cmd):
        if cmd.is_timed():
            self.check_access(cmd.addr_int, cmd.access_level)
        return self._apply(cmd)

    def _apply(self, cmd):
        if isinstance(cmd, CloseSession):
            self._deprecate_time = 0

    def _commit(self, cmd, out):
        if cmd.has_response:
            cmd.set_response(out)
            return cmd.response


class BrokerInterface(_Interface):

    def __init__(self, mqtt):
        super(BrokerInterface, self).__init__()
        self.mqtt = mqtt
        self.bus_id = None
        self.response = dict()
        self._is_busy = False
        self._stopped = False
        self._request_event = threading.Event()

    def set_stopped(self):
        self._stopped = True

    def get_event(self):
        return None

    def get_ex_cmd(self):
        return None

    def set_event_handler(self, _):
        pass

    def set_external_cmd_handler(self, _):
        pass

    def set_bus_id(self, bus_id):
        self.bus_id = bus_id

    def send(self, cmd):
        if self._stopped is True:
            return None
        if self.bus_id is None:
            raise BaseException('Bus_ID is not set')

        if self.has_failed and cmd.addr_int in self.has_failed:
            self.check_connect(cmd.addr_int)

        # ToDo нужны пароли!!!
        # return super(BrokerInterface, self).send(cmd)
        return self._apply(cmd)

    @property
    def is_busy(self):
        return self._is_busy > 0

    def set_busy(self, busy_code):
        self._is_busy = busy_code

    def on_response(self, data):
        try:
            self.response[int(data[0:2], 16)] = bytes.fromhex(data)
        finally:
            self.release_condition()

    def on_error(self, data):
        self.response[int.from_bytes(data[0:1], 'little')] = b''

    def _apply(self, cmd):
        super(BrokerInterface, self)._apply(cmd)
        data = ''.join(hex(b).replace('0x', '').rjust(2, '0') for b in cmd.pack).upper()
        flags = 'RS{}'.format(3 + cmd.framesize)

        if cmd.addr_int in self.response:
            self.response.pop(cmd.addr_int)

        self.mqtt.publish(
            topic=str(TopicTcp(mqtt.SEND, self.bus_id)),
            payload='#'.join([data, flags]))

        return self.check_response(cmd)

    def check_response(self, cmd):
        self._request_event.wait(TIMEOUT if str.isdigit((str(TIMEOUT))) else None)
        self._request_event.clear()
        if cmd.addr_int in self.response:
            r = self.response.pop(cmd.addr_int)
            try:
                return self._commit(cmd, r)
            except:
                return self.check_response(cmd)
        else:
            if cmd.addr_int not in self.has_failed:
                self.has_failed.append(cmd.addr_int)
            raise TimeOutError(cmd)

    def check_connect(self, address):
        cmd = None
        while True:
            try:
                if cmd is None:
                    cmd = CheckConnect(address)
                    r = self._apply(cmd)
                else:
                    r = self.check_response(cmd)
            except BadConnectResponse:
                continue
            except BaseException:
                break
            else:
                if r.value:
                    self.has_failed.remove(cmd.addr_int)
                break

    def release_condition(self):
        if not self._request_event.is_set():
            self._request_event.set()


class SocketInterface(_Interface):
    def __init__(self, host, port, timeout=1, p1='', p2='', p3=''):
        super(SocketInterface, self).__init__(p1, p2, p3)
        self._s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._s.settimeout(timeout)
        try:
            self._s.connect((host, port))
        except BaseException as ex:
            # print('Не удалось установить соединение с {}:{}'.format(host, port))
            raise TimeOutError(None)

    def _apply(self, cmd):
        super(SocketInterface, self)._apply(cmd)
        out = b''
        size = cmd.framesize
        try:
            self._s.send(cmd.pack)
            while len(out) < size + 3:
                out += self._s.recv(size + 3 - len(out))
        except socket.timeout:
            raise TimeOutError(cmd)
        except BaseException as ex:
            raise ex

        return self._commit(cmd, out)


# i = SocketInterface('10.10.1.32', 4001, p1='111111', p2='222222')
# res = i.send(SerialCommand(30))
# print(res)
# res = i.send(CurrentDateTime(30))
# print(res)
# # res = i.send(OpenCloseTime(30, 0))
# res = i.send(StoredEnergy(30, period=0x3, tariff=1, month=10))
# powerP0 = i.send(AUXPower(30, power_id=0, phase=0))
# rate1 = i.send(AUXPowerRate(30, phase=0))
# voltage1 = i.send(AUXVoltage(30, phase=1))
# amperage1 = i.send(AUXAmperage(30, phase=1))
# angle12 = i.send(AUXAngle(30, phase=1))
# frequency = i.send(AUXFrequency(30))
# temp = i.send(AUXTemp(30))
# res = i.send(ReadLoadState(30))
# # res = i.send(SetLoad(30, SetLoad.OFF))
# res = i.send(CloseSession(30))
