from __future__ import print_function

import socket
import threading

from spread_core.mqtt import TopicDali, SEND, DOUBLE_SEND_FLAG, FORCE_ANSWER_FLAG
from spread_core.protocols.dali import frame as frame
from spread_core.protocols.dali.command import Command
from spread_core.protocols.dali.frame import BackwardModuleError
from spread_core.protocols.dali.gear import general as gear
from spread_core.protocols.dali.gear.events import Event
from spread_core.protocols.mercury.errors import TimeOutError
from spread_core.tools.settings import logging


class DaliInterface:
    _is_busy = 0
    _response = None
    _request_event = threading.Event()
    _last_command = None
    _events = []
    _external = []
    controller_id = None
    module_id = None
    channel = None
    event_handler = None
    external_cmd_handler = None

    def __init__(self, mqtt_client, timeout):
        self._mqtt_client = mqtt_client
        self.timeout = timeout
        self._stopped = False

    def set_stopped(self):
        self._stopped = True

    def set_bus_id(self, controller_id, module_id, channel):
        self.controller_id = controller_id
        self.module_id = module_id
        self.channel = channel

    @property
    def is_busy(self):
        return self._is_busy > 0

    def set_busy(self, busy_code):
        self._is_busy = busy_code

    def on_resp(self, response, flags=''):
        flags = flags.split(':') if len(flags) > 0 else []
        response = bytes.fromhex(response) if len(response) > 0 else b''

        command = self._last_command
        if command:
            if response == command.frame.pack:
                command.on_commit()
                logging.debug('  -> ✓: {}'.format(str_bytes(response)))
                if command.is_commited and not command.is_query:
                    self.release_condition()
            elif len(response) == 3:
                if response[0] & 1 == 0:
                    self.on_dali2_event(response, flags)
                else:
                    self.on_unknown_pack(response)
            elif not command.is_commited:
                self.on_unknown_pack(response)
            elif self._last_command:
                self.on_dali_resp(response, flags)
        elif len(response) == 3 and response[0] & 1 == 0:
            self.on_dali2_event(response, flags)
        elif len(response) > 0:
            self.on_unknown_pack(response)

    def on_unknown_pack(self, pack):
        if self.external_cmd_handler:
            self._external.append(pack)
            if not self.external_cmd_handler.is_set():
                self.external_cmd_handler.set()
            return

        logging.debug('UNKNOWN FRAME {}'.format(str_bytes(pack)))

    def on_dali_resp(self, response, flags):
        command = self._last_command
        command.on_response()
        try:
            if 'E' in flags:
                result = command.response(frame.BackwardModuleError())
            elif len(response) == 0:
                result = command.response(None)
            else:
                result = command.response(frame.BackwardFrame(response))

            self._response = result

            _flags_str = 'flags: [{}]'.format(', '.join(flags)) if len(flags) > 0 else ''
            logging.debug('    <- {}'.format('; '.join([str(result), _flags_str])))
        except BaseException as ex:
            logging.error('[{}]: {}'.format(response, str(ex)))
        finally:
            self.release_condition()

    def on_dali2_event(self, response, flags):
        if self.event_handler:
            event = Event.of(response)
            self._events.append(event)
            if not self.event_handler.is_set():
                self.event_handler.set()

    def release_condition(self):
        self._request_event.set()

    def send(self, command):
        if self._stopped is True:
            return BackwardModuleError()

        s = self._mqtt_client

        assert isinstance(command, Command)

        if isinstance(command, gear._GearCommand) and command.device_type > 0:
            self.send(gear.EnableDeviceType(command.device_type))

        message = command.frame.pack

        to_topic = str(TopicDali(SEND, self.controller_id, self.module_id, bin(1 << self.channel).replace('0b', '')[::-1]))

        data = ''.join(hex(b).replace('0x', '').rjust(2, '0') for b in message).upper()

        flags = []
        if command.is_config:
            flags += DOUBLE_SEND_FLAG
        if command.is_query:
            flags += FORCE_ANSWER_FLAG

        if len(flags) > 0:
            data += '#' + ':'.join(flags)

        command.on_send()
        self._last_command = command
        self._response = None

        s.publish(to_topic, data)
        logging.debug(u"-> {}".format(command))

        self._request_event.wait(self.timeout)
        if self._last_command and self._last_command.is_query and self._response is None:
            self._response = command.response(frame.BackwardModuleError())
            logging.info('      <- NOT ANSWERED')
        self._last_command = None
        self._request_event.clear()

        if (isinstance(self._response, BackwardModuleError) or self._response is None or self._response._value is None) and command.need_retry:
            logging.info('RESEND...')
            self._response = self.send(command)

        return self._response

    def set_event_handler(self, event_handler):
        self.event_handler = event_handler

    def set_external_cmd_handler(self, external_cmd_handler):
        self.external_cmd_handler = external_cmd_handler

    def get_event(self):
        if len(self._events) > 0:
            return self._events.pop(0)
        return None

    def get_ex_cmd(self) -> bytes:
        if len(self._external) > 0:
            return self._external.pop(0)
        return b''


class SocketInterface:
    def __init__(self, host, port, timeout=1, p1='', p2='', p3=''):
        self._s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._s.settimeout(timeout)
        try:
            self._s.connect((host, port))
            out = self._s.recv(1024)
            print(out)
        except BaseException as ex:
            # print('Не удалось установить соединение с {}:{}'.format(host, port))
            raise TimeOutError(None)

    def set_bus_id(self, controller_id, module_id, channel):
        self.controller_id = controller_id
        self.module_id = module_id
        self.channel = channel

    def send(self, command):
        assert isinstance(command, Command)
        message = command.frame.pack

        bite1 = 0x0
        if command.is_config:
            bite1 = bite1 | 0x1
        if len(message) == 3:
            bite1 = bite1 | 0x2
        if command.is_forced:
            bite1 = bite1 | 0x4

        message = b'\x01' + bite1.to_bytes(1, 'little') + (self.channel + 1).to_bytes(1, 'little') + message
        message = b'\xe1\x03' + (len(message)).to_bytes(1, 'little') + message

        command.on_send()
        logging.debug(u"-> {}".format(command))
        self._s.send(message)
        try:
            out = self._s.recv(1024)
            out = out[5:]
            while out == command.frame.pack:
                command.on_commit()
                logging.debug('  -> ✓: {}'.format(str_bytes(out)))
                out = self._s.recv(1024)
                out = out[5:]
        except socket.timeout as ex:
            resp = None
            logging.info('  <- EMPTY: {}'.format(command))
        else:
            resp = frame.BackwardFrame(out)
            resp = command.response(resp)
            command.on_response()

            if len(out) == 0:
                logging.debug('    <- X {}'.format(None))
            else:
                logging.debug('    <- {}'.format(str_bytes(out)))

        return resp


def str_bytes(bytes):
    return ' '.join(hex(b)[2:].rjust(2, '0') for b in bytes)
