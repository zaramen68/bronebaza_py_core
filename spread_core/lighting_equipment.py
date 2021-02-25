import json

from spread_core.bam.dali.equipment import LightingEquipment
from spread_core.errors.project_errors import EngineryError
from spread_core.mqtt import of, TopicProject, TopicCommandTros3, TopicState, TopicCommand
from spread_core.mqtt.variables import VariableTRS3, VariableReader, VariableJocket
from spread_core.tools.service_launcher import Launcher
from spread_core.tools.settings import logging, config

PROJECT_ID = config['PROJECT_ID']


class LightingEquipmentLauncher(Launcher):
    def __init__(self):
        self._manager = LightingEquipment(PROJECT_ID)
        self._manager.set_broker(self.mqttc)
        super(LightingEquipmentLauncher, self).__init__()

    def on_message(self, mosq, obj, msg):
        super(LightingEquipmentLauncher, self).on_message(mosq, obj, msg)
        topic = of(msg.topic)
        try:
            if isinstance(topic, TopicCommandTros3):
                var = VariableTRS3(VariableReader(msg.payload))
                self._manager.on_tros3_command(topic, var)
            else:
                payload = msg.payload.decode()
                if isinstance(topic, TopicCommand):
                    var = VariableJocket(json.loads(payload))
                    self._manager.on_command(topic, var)
                elif isinstance(topic, TopicState):
                    jocket = VariableJocket(json.loads(payload))
                    if topic.entity_addr.funit_type in self._manager.EVENT_TOPICS:
                        self._manager.on_event(topic, jocket)
                    else:
                        self._manager.on_state(topic, jocket)
                elif isinstance(topic, TopicProject):
                    self._manager.on_project(data=payload)
                else:
                    logging.debug('[{}] => {}'.format(msg.topic, payload))
        except EngineryError as ex:
            logging.warning(ex)
        except BaseException as ex:
            logging.exception(ex)

    def on_exit(self, sig, frame):
        try:
            self._manager.on_exit()
        except BaseException as ex:
            logging.exception(ex)
        super(LightingEquipmentLauncher, self).on_exit(sig, frame)


def run():
    LightingEquipmentLauncher()


if __name__ == '__main__':
    run()
