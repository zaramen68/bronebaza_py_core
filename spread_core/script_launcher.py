import json

import spread_core.mqtt as mqtt
from spread_core.bam.scripter import Scripter
from spread_core.mqtt.variables import VariableTRS3, VariableReader
from spread_core.tools.service_launcher import Launcher, logging
from spread_core.tools.settings import config

PROJECT_ID = config['PROJECT_ID']


class ScriptLauncher(Launcher):
    _dumped = False

    def __init__(self):
        self._manager = Scripter(PROJECT_ID, self.mqttc)
        super(ScriptLauncher, self).__init__()

    def on_message(self, mosq, obj, msg):
        super(ScriptLauncher, self).on_message(mosq, obj, msg)
        try:
            topic = mqtt.of(msg.topic)
            if isinstance(topic, (mqtt.TopicCommandTros3, mqtt.TopicStateTros3)):
                variable = VariableTRS3(VariableReader(msg.payload))
            elif isinstance(topic, (mqtt.TopicState, mqtt.TopicCommand)):
                payload = msg.payload.decode()
                variable = mqtt.variables.VariableJocket(json.loads(payload))
            else:
                return

            self._manager.on_message(topic, variable)
        except BaseException as ex:
            logging.exception(ex)

    def on_exit(self, sig, frame):
        self._manager.on_exit()
        super(ScriptLauncher, self).on_exit(sig, frame)


def run():
    ScriptLauncher()


if __name__ == '__main__':
    run()
