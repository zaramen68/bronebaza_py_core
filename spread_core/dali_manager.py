import json

from spread_core.bam import generator
from spread_core.errors.project_errors import ClassifierError
from spread_core.mqtt import TopicDali, TopicCommand, of, TopicProject, TopicState
from spread_core.mqtt.variables import VariableJocket
from spread_core.protocols.dali.driver.dali_interface import DaliInterface
from spread_core.tools.service_launcher import Launcher
from spread_core.tools.settings import *

PROJECT_ID = config['PROJECT_ID']
MANAGER_TYPE = config['MANAGER_TYPE']
MANAGER_ID = config['MANAGER_ID']
COMMUNICATE_TIMEOUT = config['COMMUNICATE_TIMEOUT'] if 'COMMUNICATE_TIMEOUT' in config else 1


class DaliManagerLauncher(Launcher):
    def __init__(self):
        self._manager = generator.generate_manager(PROJECT_ID, MANAGER_TYPE, MANAGER_ID)
        self._manager.set_broker(self.mqttc, DaliInterface(self.mqttc, COMMUNICATE_TIMEOUT))
        super(DaliManagerLauncher, self).__init__()

    def on_message(self, mosq, obj, msg):
        super(DaliManagerLauncher, self).on_message(mosq, obj, msg)
        try:
            topic = of(msg.topic)
            payload = msg.payload.decode()
            if isinstance(topic, TopicDali):
                self._manager.send_interface.on_resp(*payload.split('#'))
            elif isinstance(topic, TopicCommand):
                self._manager.on_command(topic, VariableJocket(json.loads(payload)))
            elif isinstance(topic, TopicProject):
                self._manager.on_project(topic=topic, data=payload)
            elif isinstance(topic, TopicState):
                self._manager.on_state(topic=topic, jocket=payload)
            else:
                logging.debug('[{}] => {}'.format(msg.topic, payload))
        except ClassifierError as ex:
            logging.error(ex)
        except BaseException as ex:
            logging.exception(ex)

    def on_exit(self, sig, frame):
        self._manager.on_exit()
        super(DaliManagerLauncher, self).on_exit(sig, frame)


def run():
    DaliManagerLauncher()


if __name__ == '__main__':
    run()
