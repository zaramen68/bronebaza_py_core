import json
import logging
import os
import threading

from spread_core.bam.handling import triggers, actions
from spread_core.bam.schedule import const
from spread_core.errors.project_errors import InitError
from spread_core.tools import manager_interface, settings


class Scripter(manager_interface.ManagerOfBroker):
    def __init__(self, project_id, _mqttc):
        self.stopped = False
        self.stack = []
        super(Scripter, self).__init__(_mqttc)
        self.project_id = project_id
        self.triggers = {}
        self.values = {}
        self.step = threading.Event()
        self.exec_thread = threading.Thread(target=self.execution, name='ExecThread')
        self.exec_thread.start()

    def start(self):
        triggers_path = settings.config[settings.TRIGGERS]
        if os.path.isfile(triggers_path):
            with open(triggers_path, 'r') as file:
                data = file.read()
            if not data:
                data = '[]'
            try:
                data = json.loads(data)
            except BaseException as ex:
                raise InitError('Ошибка парсинга файла "{0}": {1}'.format(triggers_path, ex))
            for trigger_data in data:
                try:
                    trigger = triggers.of(trigger_data)
                    self.triggers[trigger] = []
                    for action_data in trigger_data[const.ACTIONS]:
                        try:
                            action = actions.action_of_data(action_data)
                            self.triggers[trigger].append(action)
                        except BaseException as ex:
                            logging.warning(ex)
                        else:
                            if action.conditioned:
                                for condition in action.conditions:
                                    self.subscribe(condition.topic, log=True)
                    if len(self.triggers[trigger]) == 0:
                        self.triggers.pop(trigger)
                    elif isinstance(trigger, triggers.BrokerTrigger):
                        self.subscribe(trigger.topic, log=True)
                except BaseException as ex:
                    logging.warning(ex)

            if len(self.triggers) == 0:
                raise InitError('Файл "{}" не содержит ни одного триггера!'.format(triggers_path))
        else:
            raise InitError('{} не существует!'.format(triggers_path))

    def on_message(self, topic, variable):
        self.values[str(topic)] = variable.value
        for trigger in self.triggers:
            if isinstance(trigger, triggers.BrokerTrigger):
                if trigger.check(topic, variable):
                    for action in self.triggers[trigger]:
                        if isinstance(action, actions.Action):
                            self.stack.append((action, variable.value))
                            if not self.step.is_set():
                                self.step.set()

    def on_exit(self):
        self.stopped = True
        self.step.set()

    def get_condition_value(self, key):
        if key in self.values:
            return self.values[key]

        return None

    def execution(self):
        while self.stopped is False:
            while len(self.stack) > 0:
                if self.stopped:
                    return
                try:
                    action, rec_value = self.stack.pop(0)
                    action.execute(self.publish, rec_value, self.get_condition_value)
                except BaseException as ex:
                    logging.error(ex)
            self.step.clear()
            self.step.wait()
