import json
import logging
import os
from threading import Timer

from spread_core.bam.handling.triggers import DateTrigger
from spread_core.errors.project_errors import InitError
from .locations import location_of_data
from ..handling import actions
from ...tools import settings, manager_interface


class Scheduler(manager_interface.ManagerOfBroker):
    def __init__(self, p_id, _mqttc, finish):
        self.stack = None
        self.timer = None
        self.finish = finish
        super(Scheduler, self).__init__(_mqttc)

    def start(self):
        path = settings.config[settings.TASKS]
        if os.path.isfile(path):
            with open(path, 'r') as file:
                data = file.read()
            if not data:
                data = '[]'
            try:
                data = json.loads(data)
            except BaseException as ex:
                raise InitError('Ошибка парсинга файла "{0}": {1}'.format(path, ex))
            self.stack = {}
            for datum in data:
                try:
                    location = location_of_data(datum)
                    logging.debug('{}'.format(location))
                    if location.enabled:
                        for task in location.tasks:
                            logging.debug('    {}'.format(task))
                            for action in task.actions:
                                logging.debug('        {}'.format(action))

                            if task.trigger not in self.stack:
                                self.stack[task.trigger] = []
                            self.stack[task.trigger] += task.actions
                except BaseException as ex:
                    logging.exception(ex)

            self.on_timer()
        else:
            raise InitError('{} не существует!'.format(path))

    def on_timer(self):
        try:
            triggers = sorted(self.stack)
            if len(triggers) > 0:
                trigger = triggers[0]
                interval = trigger.time_left + 1
                logging.debug('SET TIMER to {0} sec FOR {1}'.format(interval, trigger))
                if self.timer:
                    self.timer.cancel()
                self.timer = Timer(interval=interval, function=self.exec_task, args=[trigger, self.stack[trigger]])
                self.timer.start()
            else:
                self.finish()
        except BaseException as ex:
            logging.exception(ex)

    def exec_task(self, _trigger: DateTrigger, _actions: list):
        logging.debug('EXECUTE {}:'.format(_trigger))
        for action in _actions:
            try:
                if isinstance(action, actions.BrokerAction):
                    action.execute(self.publish)
            except BaseException as ex:
                logging.exception(ex)

        self.on_timer()

    def on_exit(self):
        if self.timer:
            self.timer.cancel()
            self.timer = None

    def get_address(self, funit_id):
        raise NotImplemented()
