import json
import time
import paho.mqtt.client

from spread_core import mqtt
from spread_core.bam.generator import generate_manager
from spread_core.mqtt.variables import VariableJocket
# from spread_core.protocols.mercury.interface import BrokerInterface
from spread_core.tools.service_launcher import Launcher
from spread_core.mqtt.variables import VariableTRS3
from spread_core.tools.settings import logging, config

PROJECT_ID = config['PROJECT_ID']
BROKER_HOST = config['BROKER_HOST']
BROKER_PORT = config['BROKER_PORT']
BROKER_USERNAME = config['BROKER_USERNAME']
BROKER_PWD = config['BROKER_PASSWORD']
TCP_DEV = config['TCP_DEV']
CONTROLLERS = config['CONTROLLERS']
PROJECT = config['PROJ']

topic_read = 'ModBus/State/{}/{}/{}/{}/{}'
# Tros3/Command/{ProjectID}/Equipment/SwitchingLightLight/{EngineryID}/{FunctionUnitIndex}/inOn&inOff
topic_light_command = 'Tros3/Command/{}/Equipment/SwitchingLightLight/{}'
# Tros3/State/{ProjectID}/Equipment/SwitchingLightLight/{EngineryID}/{FunctionUnitIndex}: [isOnId - 2]
topic_light_state = 'Tros3/State/{}/Equipment/SwitchingLightLight/{}'
topic_dump = 'Tros3/State/{}/{}/{}'
light_topics = config['TOPIC_SUB']

current_milli_time = lambda: int(round(time.time() * 1000))

class Controller:
    def __init__(self, mqtt, t_gap, *args):
        self._t_gap = t_gap
        self._mqtt = mqtt
        self._dev = args
        self._time = current_milli_time()

    def devices(self):
        return self._dev

class DoorsSw:
    def __init__(self, mqtt, t_gap, *args):
        self._t_gap = t_gap
        self._mqtt = mqtt
        self._dev = args
        self._time = current_milli_time()
        self._topicValues = {
                      'openId': True,
                      'isOpeningId':False,
                      'isOpenedId':False,
                      'closeId': True,
                      'isClosingId':False,
                      'isClosedId':False,
                      'stopId':False,
                      'isStoppedId':False,
                      'setClosenessLevelId':True,
                      'closenessLevelId':10000,
                    }

    def devices(self):
        return self._dev

    def write_to_bro(self, topId, num, value):
        out = VariableTRS3(None, topId, num, value)
        self._mqtt.publish(topic=topic_dump.format(PROJECT, str(topId), str(num)), payload=out.pack())
        #logging.debug('[  <-]: {}'.format(out))

    def work(self, msg, time):
        if (time - self._time) >= self._t_gap:
            out = msg.payload.decode()
            tpc = msg.topic.split('/')
            if len(out) !=20:
                return
            for dev_ice in self._dev:
                device = dev_ice[0]
                if str(device['di']) == tpc[6]:
                    value = int(out[19], 16)
                    if value == 1:
                        v = True
                    elif value == 0:
                        v = False
                    if device['value'] is None or device['value'] != v:
                        #   initial values
                        device['value'] = v
                        num = 0
                        for key, value in self._topicValues.items():
                            if key == 'isOpenedId':
                                self.write_to_bro(device['topicId'], num, v)
                            else:
                                self.write_to_bro(device['topicId'], num, value)
                            num+=1
            self._time = time

class Light:
    def __init__(self, mqtt, t_gap, *args):
        self._t_gap = t_gap
        self._mqtt = mqtt
        self._time = current_milli_time()
        self._dev = args
        self._topicValues = {'value': None,}

    def devices(self):
        return self._dev

    def work(self, msg, time):
        if (time - self._time) >= self._t_gap:
            out = msg.payload.decode()
            # if len(out) != 23:
            #     return
            for dev_ice in self._dev:
                device = dev_ice[0]
                try:
                    tt=out[18:22]
                    tk=int(tt, 16)
                    tk = tk + 27315
                    # tk = 27315
                    if self._topicValues['value'] is None:
                        #   initial values
                        self._topicValues['value'] = tk
                        out = VariableTRS3(None, self._topicValues['topicId'], 0, tk)
                        top_out = topic_dump.format(PROJECT, self._topicValues['topicId'], '0')
                        self._mqtt.publish(topic=topic_dump.format(PROJECT, self._topicValues['topicId'], '0'), payload=out.pack())
                        #logging.debug('[  <-]: {}'.format(out))
                    elif (abs(self._topicValues['value'] - tk) > 10):
                        self._topicValues['value'] = tk
                        out = VariableTRS3(None, device['topicId'], 0, tk)
                        top_out = topic_dump.format(PROJECT, self._topicValues['topicId'], '0')
                        self._mqtt.publish(topic=top_out, payload=out.pack())
                        # self._mqtt.publish(topic=topic_dump.format(PROJECT, self._topicValues['topicId'], '0'),
                        #                    payload=out.pack())
                        # logging.debug('[  <-]: {}'.format(out))
                except BaseException as ex:
                    logging.exception(ex)
            self._time = time


class Thermometer:
    def __init__(self, mqtt, t_gap, *args):
        self._t_gap = t_gap
        self._mqtt = mqtt
        self._time = current_milli_time()
        self._dev = args
        self._topicValues = {'value': None,}

    def devices(self):
        return self._dev

    def work(self, msg, time):
        if (time - self._time) >= self._t_gap:
            out = msg.payload.decode()
            if len(out) != 23:
                return
            for dev_ice in self._dev:
                device = dev_ice[0]
                try:
                    tt=out[18:22]
                    tk=int(tt, 16)
                    tk = tk + 27315
                    # tk = 27315
                    if self._topicValues['value'] is None:
                        #   initial values
                        self._topicValues['value'] = tk
                        out = VariableTRS3(None, self._topicValues['topicId'], 0, tk)
                        top_out = topic_dump.format(PROJECT, self._topicValues['topicId'], '0')
                        self._mqtt.publish(topic=topic_dump.format(PROJECT, self._topicValues['topicId'], '0'), payload=out.pack())
                        #logging.debug('[  <-]: {}'.format(out))
                    elif (abs(self._topicValues['value'] - tk) > 10):
                        self._topicValues['value'] = tk
                        out = VariableTRS3(None, device['topicId'], 0, tk)
                        top_out = topic_dump.format(PROJECT, self._topicValues['topicId'], '0')
                        self._mqtt.publish(topic=top_out, payload=out.pack())
                        # self._mqtt.publish(topic=topic_dump.format(PROJECT, self._topicValues['topicId'], '0'),
                        #                    payload=out.pack())
                        # logging.debug('[  <-]: {}'.format(out))
                except BaseException as ex:
                    logging.exception(ex)
            self._time = time



class ModBusManagerLauncher:

    def __init__(self):
        self._time = current_milli_time()
        self.mqttc = paho.mqtt.client.Client()
        self.mqttc.username_pw_set(BROKER_USERNAME, BROKER_PWD)
        self.mqttc.on_connect = self.on_connect
        self.mqttc.on_subscribe = self.on_subscribe
        self.mqttc.on_message = self.on_message
        self.mqttc.connect(BROKER_HOST, BROKER_PORT)

        self.controllers=[]
        self.load_controllers()

        for dev in TCP_DEV:
            #self.providers.append(ModBusProvider(self.mqttc, dev['host'], dev['port'], dev['dev']))
            for device in dev['dev']:
                topic_mqtt = topic_read.format(PROJECT, dev['host'], device['type'], str(device['id']), str(device['reg']))
                self.mqttc.subscribe(topic=topic_mqtt, qos=1)
        #super(ModBusManagerLauncher, self).__init__()
        self.mqttc.loop_forever()

    def load_controllers(self):
        for cntr in CONTROLLERS:
            if cntr['type'] == 'door_sw':
                self.controllers.append(DoorsSw(self.mqttc, cntr['t_gap'], cntr['dev']))
            elif cntr['type'] == 'thermometer':
                self.controllers.append(Thermometer(self.mqttc, cntr['t_gap'], cntr['dev']))
            elif cntr['type'] == 'light':
                self.controllers.append(Light(self.mqtt, cntr['t_gap'], cntr['dev']))
            # elif cntr['type'] == 'blackout':
            #     self.controllers.append(Blackout(self.mqttc, cntr['dev']))

    def on_connect(self, mqttc, userdata, flags, rc):
        if rc==0:
            print("connected OK Returned code=",rc)
        else:
            print("Bad connection Returned code=",rc)

    def on_subscribe(self, mqttc, userdata, mid, granted_qos):
        print("Subscribed: " + str(mid) + " " + str(granted_qos))

    def of(self, topic):
        arr = topic.split('/')
        return arr



    def on_message(self, mqttc, userdata, msg):
        #super(ModBusManagerLauncher, self).on_message(mosq, obj, msg)

        try:
            topic = self.of(msg.topic)
            for cntr in self.controllers:
                for device in cntr.devices():
                    if topic[3] == device[0]['host']:
                        cntr.work(msg, self._time)

        except BaseException as ex:
            logging.exception(ex)

    def on_exit(self, sig, frame):
        self._manager.on_exit()
        super(ModBusManagerLauncher, self).on_exit(sig, frame)


def run():
    ModBusManagerLauncher()


if __name__ == '__main__':
    run()
