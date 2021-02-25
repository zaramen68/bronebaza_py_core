import json

from lom.interface import LomInterface
from spread_core.bam import generator
from spread_core.errors.project_errors import CoreError, InitError
from spread_core.mqtt import spread, mqtt, variables
from spread_core.tools.service_launcher import Launcher
from spread_core.tools.settings import *

PROJECT_ID = config['PROJECT_ID']
MANAGER_TYPE = config['MANAGER_TYPE']
MANAGER_ID = config['MANAGER_ID']


class LomManagerLauncher(Launcher):
    def __init__(self):
        self._manager = generator.generate_manager(PROJECT_ID, MANAGER_TYPE, MANAGER_ID)
        self._manager.set_broker(self.mqttc, LomInterface())
        super(LomManagerLauncher, self).__init__()

    def on_message(self, mosq, obj, msg):
        super(LomManagerLauncher, self).on_message(mosq, obj, msg)
        try:
            payload = msg.payload.decode()
            if 'Jocket/Command' in msg.topic:
                topic = mqtt.of(msg.topic)
                if isinstance(topic, mqtt.TopicCommand):
                    mqtt_var = variables.VariableJocket(json.loads(payload))
                    addr = spread.address.ProviderAddress(PROJECT_ID, topic.entity_addr.manager_type,
                                                          topic.entity_addr.manager_id, topic.entity_addr.provider_type,
                                                          topic.entity_addr.provider_id, topic.entity_addr.funit_type)
                    self._manager.on_command(spread.topic.Set(addr), spread.variable.Variable(mqtt_var.value))
            else:
                topic = spread.topic.topic_of(msg.topic)
                if isinstance(topic, spread.topic.Set):
                    self._manager.on_command(topic, spread.variable.Variable(json.loads(payload)))
                elif isinstance(topic, spread.topic.TopicProject):
                    self._manager.on_project(topic=topic, data=payload)
                else:
                    logging.debug('[{}] => {}'.format(msg.topic, payload))
        except InitError as ex:
            logging.error(ex)
            self.on_exit(0, 0)
        except CoreError as ex:
            logging.error(ex)
        except BaseException as ex:
            logging.exception(ex)

    def on_exit(self, sig, frame):
        self._manager.on_exit()
        super(LomManagerLauncher, self).on_exit(sig, frame)


def run():
    LomManagerLauncher()


if __name__ == '__main__':
    run()
