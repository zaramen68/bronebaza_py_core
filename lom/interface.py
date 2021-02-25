import base64
import json
import logging
import threading

import cbor
import paho.mqtt.client

from . import commands

LOM_HOST = 'LOM_HOST'
LOM_PORT = 'LOM_PORT'
LOM_USER = 'LOM_USER'
LOM_PASSWORD = 'LOM_PASSWORD'

UPLINK = 'airbit/light/ctrl/sample'
DOWNLINK = 'send/data/'


class LomInterface(threading.Thread):
    def __init__(self):
        super(LomInterface, self).__init__()
        self.stopped = False
        self.ready = False
        self._mqttc = None
        self._address = None
        self._auth = None
        self._send_topic = None
        self._dump_topic = None
        self.event_handler = None
        self.external_cmd_handler = None
        self._events = []
        self._external = []
        # self._sended = {}

    def set_event_handler(self, handler: threading.Event):
        self.event_handler = handler

    def set_external_cmd_handler(self, handler: threading.Event):
        self.external_cmd_handler = handler

    def run(self):
        self.do_connect()
        self.mqttc.loop_forever()

    def set_config(self, host, port, login, pwd, send_topic, dump_topic):
        self._address = (host, port)
        self._auth = (login, pwd)
        self._send_topic = send_topic
        self._dump_topic = dump_topic

    def send(self, command: commands.LCommand, mc=False, *args, **kwargs):
        try:
            topic = self._send_topic + command.dev_eui
            stack = [self._prepare(cmd, mc) for cmd in command.split(5)]
        except Exception as ex:
            logging.error(ex)
        else:
            logging.debug(f'-> {command}')
            for data in stack:
                try:
                    self.mqttc.publish(topic, data)
                except BaseException as ex:
                    logging.error(ex)

    @staticmethod
    def _prepare(command, is_mc: bool):
        data = command.pack
        data = cbor.dumps(data)
        data = base64.b64encode(data).decode()
        data = {'data': data, 'fport': command.fport}
        if is_mc is False:
            data['dev_eui'] = command.dev_eui
        else:
            data['mcaddr'] = command.dev_eui
        data = json.dumps(data)

        return data

    def do_connect(self):
        if not self.stopped:
            logging.info('Try connect to {}:{}'.format(*self._address))
            self.mqttc.connect(host=self._address[0], port=self._address[1])

    def set_stopped(self):
        self.stopped = True
        if self.mqttc:
            try:
                self.mqttc.disconnect()
                self.mqttc.loop_stop(True)
            except BaseException as ex:
                logging.error(ex)

    @property
    def mqttc(self):
        if self._mqttc is None:
            _mqttc = paho.mqtt.client.Client(userdata=self.__class__.__name__, client_id='qwe', clean_session=True)
            _mqttc.on_connect = self.on_connect
            _mqttc.on_message = self.on_message
            _mqttc.on_disconnect = self.do_connect
            _mqttc.on_subscribe = self.on_subscribe
            _mqttc.username_pw_set(*self._auth)
            self._mqttc = _mqttc
        return self._mqttc

    def on_connect(self, mosq, obj, flags, rc):
        connect_results = ['Connection successful',
                           'Connection refused - incorrect protocol version',
                           'Connection refused - invalid client identifier',
                           'Connection refused - server unavailable',
                           'Connection refused - bad username or password',
                           'Connection refused - not authorised']
        if rc < len(connect_results):
            logging.info(connect_results[rc])
            if rc != 0:
                self.ready = False
                self.do_connect()
            else:
                self.ready = True
                self.mqttc.subscribe(self._send_topic + '#')
                self.mqttc.subscribe(self._dump_topic)
        else:
            logging.warning("rc: " + str(rc))

    def on_subscribe(self, client, userdata, mid):
        logging.debug('success')

    def on_message(self, mosq, obj, msg):
        try:
            data = json.loads(msg.payload.decode())
            encoded = base64.b64decode(data['data'])
            decoded = cbor.loads(encoded)
            # logging.debug(f'BASE64: [{msg.topic}]: {data}')
            # logging.debug(f'  CBOR: [{msg.topic}]: {encoded}')
            # logging.debug(f'  DATA: [{msg.topic}]: {decoded}')

            try:
                dev_eui = data['mcaddr'] if 'mcaddr' in data else data['dev_eui']
                fport = data['fport']

                if msg.topic == self._dump_topic:
                    if fport == 1:
                        handler = None
                        response = commands.response_of(dev_eui, decoded)
                        # _target = None
                        # if dev_eui in self._sended:
                        #     for cmd in self._sended[dev_eui][::-1]:
                        #         if cmd._cmd_id == response._cmd_id:
                        #             if _target is None:
                        #                 _target = cmd
                        #                 self._sended[dev_eui].remove(_target)
                        #             elif _target:
                        #                 logging.warning(f'    <- X: {cmd}')
                        #                 self._sended[dev_eui].remove(cmd)
                        #
                        #     if _target:
                        if response.__class__ == commands.LAnswer:
                            if not response.success:
                                logging.warning(f'    <- X: {response}')
                            else:
                                logging.debug(f'    <- ✓: {response}')
                        else:
                            self._events.append(response)
                            handler = self.event_handler

                    else:
                        event = commands.event_of(dev_eui, decoded)
                        self._events.append(event)
                        handler = self.event_handler
                else:
                    command = commands.request_of(dev_eui, decoded)
                    logging.debug(f'  -> ✓: {command}')
                    # if dev_eui not in self._sended:
                    #     self._sended[dev_eui] = []
                    # self._sended[dev_eui].append(command)
                    self._external.append(command)
                    handler = self.external_cmd_handler

                if handler and not handler.is_set():
                    handler.set()
            except Exception as ex:
                logging.exception(ex)

        except BaseException as ex:
            logging.exception(ex)

    def get_event(self):
        if len(self._events) > 0:
            return self._events.pop(0)
        return None

    def get_ex_cmd(self) -> bytes:
        if len(self._external) > 0:
            return self._external.pop(0)
        return b''

    def exit_handler(self, sig, frame):
        logging.debug('exiting...')
        self.stopped = True
        if self.mqttc:
            try:
                self.mqttc.disconnect()
                self.mqttc.loop_stop(True)
            except BaseException as ex:
                logging.error(ex)
