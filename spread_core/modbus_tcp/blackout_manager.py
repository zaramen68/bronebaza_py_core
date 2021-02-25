import json
import time
import paho.mqtt.client


from spread_core.mqtt.variables import VariableJocket

from spread_core.tools.settings import config

PROJECT_ID = config['PROJECT_ID']
BROKER_HOST = config['BROKER_HOST']
BROKER_PORT = config['BROKER_PORT']
BROKER_USERNAME = config['BROKER_USERNAME']
BROKER_PWD = config['BROKER_PASSWORD']
TCP_DEV = config['TCP_DEV']
BLACKOUT_DEV = config['BLACKOUT_DEV']
PROJECT = config['PROJ']

topic_read = 'ModBus/State/{}/{}/{}/{}/{}'
topic_dump = 'Tros3/State/{}/{}/{}'
light_topics = config['TOPIC_SUB']
saved_light = config['SAVED_DATA']
topic_pub = config['TOPIC_PUB']
shuxer1 = config['SHUXER_1']
shuxer2 = config['SHUXER_2']




class Blackout:
    def __init__(self):

        self._is_shuxer = False
        self._reg = 0
        self._mask = []
        self._mqtts = paho.mqtt.client.Client()
        self._mqtts.username_pw_set(BROKER_USERNAME, BROKER_PWD)
        self._mqtts.on_connect = self.on_connect
        self._mqtts.on_subscribe = self.on_subscribe
        #  self._manager = generate_manager(PROJECT_ID, MANAGER_TYPE, MANAGER_ID)
        # self._manager.set_broker(self.mqttc, BrokerInterface(self.mqttc))
        self._mqtts.on_message = self.on_message
        self._mqtts.connect(BROKER_HOST, BROKER_PORT)
        for topic_to_read, value in light_topics.items():
            self._mqtts.subscribe(topic=topic_to_read, qos=1)
        for dev in TCP_DEV:
            for device in dev['dev']:
                topic_mqtt = topic_read.format(PROJECT, dev['host'], device['type'], str(device['id']), str(device['reg']))
                self._mqtts.subscribe(topic=topic_mqtt, qos=1)

        for dev in BLACKOUT_DEV['dev']:
            self._mask.append(None)
        self._mqtts.loop_forever(retry_first_connection=True)



    def on_connect(self, _mqtts, userdata, flags, rc):
        if rc==0:
            print("Blackout connected OK Returned code=",rc)
        else:
            print("Blackout Bad connection Returned code=",rc)

    def on_subscribe(self, _mqtts, userdata, mid, granted_qos):
        print("Blackout Subscribed: " + str(mid) + " " + str(granted_qos))


    def on_message(self, _mqtts, userdata, msg):
        tpc = msg.topic
        if tpc in list(light_topics.keys()):
            val = eval(msg.payload.decode())['data']['value']
            for key, value in light_topics.items():
                if key == msg.topic:
                    print("Blackout message of Light OK,  Returned code=", val)
                    light_topics[key] = val
        else:
            self.work(msg)

    def checkout(self):
        reg = 0
        for device in BLACKOUT_DEV['dev']:
            if device['topicId'] == 'night_key':
                if device['value'] == True and device['di'] == 0:
                    reg = 1
                if device['value'] == True and device['di'] == 1:
                    reg = 2

        return reg

    def work(self, msg):
        out = msg.payload.decode()
        tpc = msg.topic.split('/')
        if len(out) != 20:
            return
        for dev in BLACKOUT_DEV['dev']:

            if tpc[3] == dev['host']:
               # for dev in self._dev:
                    if str(dev['di']) == tpc[6]:
                        value = int(out[19], 16)
                        if value == 1:
                            v = True
                        elif value == 0:
                            v = False
                        if dev['value'] is None or dev['value'] != v:
                            #   initial or new values
                            dev['value'] = v
                            if dev['topicId'] == 'night_key':
                                self._mask[dev['di']] = v
                            else:
                                self._mask[dev['di']+2] = v

        if None not in  self._mask:
            self._reg = self.checkout()
            if False in self._mask[2:]:
                if self._reg != 0:
                    if self._is_shuxer != True:
                        self.shuxer()
                        return
                    else:
                        return
                else:
                    if self._is_shuxer == True:
                        self.entwarnung()
                        return
                    else:
                        return

            else:
                if self._is_shuxer == True:
                    self.entwarnung()
                    return
                else:
                    return

    def shuxer(self):
        self.save_light()
        if self._reg == 1:
            ii = 0
            self._is_shuxer = True
            while ii < len(topic_pub):

                jocket = VariableJocket.create_data(int(topic_pub[ii].split('/')[10]), 31090132,
                                                    'set', shuxer1[ii], "{00000000-0000-0000-0000-000000000000}")
                self._mqtts.publish(topic_pub[ii], jocket.pack(), qos=1)
                ii+=1

        elif self._reg == 2:
            ii = 0
            self._is_shuxer = True
            while ii < len(topic_pub):
                jocket = VariableJocket.create_data(int(topic_pub[ii].split('/')[10]), 31090132,
                                                    'set', shuxer2[ii], "{00000000-0000-0000-0000-000000000000}")
                self._mqtts.publish(topic_pub[ii], jocket.pack(), qos=1)
                ii += 1



    def save_light(self):
        for key, value in light_topics.items():
            saved_light[key.split('/')[9]] = value
    # TODO: добавить None значения в стоварь SAVED_DATA и проверку их присутствия после запоминания состояния света

    def entwarnung(self):

        for top in topic_pub:
            jocket = VariableJocket.create_data(int(top.split('/')[10]), 31090132,
                                                'set', saved_light[top.split('/')[10]], "{00000000-0000-0000-0000-000000000000}")
            self._mqtts.publish(top, jocket.pack(), qos=1)

        self._is_shuxer = False


def run():
    Blackout()


if __name__ == '__main__':
    run()
