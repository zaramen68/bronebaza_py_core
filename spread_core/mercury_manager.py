import json

from spread_core import mqtt
from spread_core.bam.generator import generate_manager
from spread_core.mqtt.variables import VariableJocket
from spread_core.protocols.mercury.interface import BrokerInterface
from spread_core.tools.service_launcher import Launcher
from spread_core.tools.settings import logging, config

PROJECT_ID = config['PROJECT_ID']
MANAGER_TYPE = config['MANAGER_TYPE']
MANAGER_ID = config['MANAGER_ID']


class MercuryManagerLauncher(Launcher):
    def __init__(self):
        self._manager = generate_manager(PROJECT_ID, MANAGER_TYPE, MANAGER_ID)
        self._manager.set_broker(self.mqttc, BrokerInterface(self.mqttc))
        super(MercuryManagerLauncher, self).__init__()

    def on_message(self, mosq, obj, msg):
        super(MercuryManagerLauncher, self).on_message(mosq, obj, msg)

        try:
            topic = mqtt.of(msg.topic)
            assert topic
            if isinstance(topic, mqtt.TopicTcp) and topic.direct == mqtt.DUMP:
                self._manager.send_interface.on_response(msg.payload.decode())
            elif isinstance(topic, mqtt.TopicCommand):
                self._manager.on_command(topic, VariableJocket(json.loads(msg.payload.decode())))
            elif isinstance(topic, mqtt.TopicTcpError):
                self._manager.send_interface.on_error(msg.payload)
            elif isinstance(topic, mqtt.TopicProject):
                self._manager.on_project(topic, msg.payload.decode())
        except BaseException as ex:
            logging.exception(ex)

    def on_exit(self, sig, frame):
        self._manager.on_exit()
        super(MercuryManagerLauncher, self).on_exit(sig, frame)


def run():
    MercuryManagerLauncher()


if __name__ == '__main__':
    run()
