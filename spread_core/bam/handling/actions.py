import json
import os
import time

from spread_core.bam.handling.conditions import Condition
from spread_core.bam.schedule import const
from spread_core.errors.project_errors import HandlingError
from spread_core.mqtt import of, variables, TopicCommandTros3, TopicCommand, ManagerAddress, EngineryAddress, \
    SubgineryAddress, EntityAddress, TopicStateTros3, TopicState
from spread_core.tools import utils


class Action:
    TYPE = None

    def __init__(self, *args, **kwargs):
        self._condition = None
        if const.CONDITION in kwargs:
            self._condition = Condition.of(kwargs[const.CONDITION])

    @property
    def conditioned(self):
        return self._condition is not None

    @property
    def conditions(self):
        if self._condition is not None:
            return [self._condition]
        return None

    def __repr__(self):
        return self.__str__()

    def data(self, *args):
        raise NotImplementedError()

    def execute(self, *args):
        raise NotImplementedError()


class BrokerAction(Action):
    TYPE = const.BROKER_TYPE
    ANY_VALUE = '$value'

    def __init__(self, *args, **kwargs):
        super(BrokerAction, self).__init__(*args, **kwargs)
        self._topic = of(kwargs[const.TOPIC])
        self._value = kwargs[const.VALUE]
        self.delay = kwargs.get(const.DELAY, 0)
        self.is_retained = kwargs.get(const.RETAINED, False)

    def __str__(self):
        return f'{self._entity_address.entity_type}[{self._entity_address.entity_id}]: "{self._command}" set {self._value}'

    @property
    def _entity_address(self) -> EntityAddress:
        return self._topic.entity_addr

    @property
    def _command(self):
        e_addr = self._entity_address
        if isinstance(e_addr, (SubgineryAddress, EngineryAddress)):
            return e_addr.funit_id
        elif isinstance(e_addr, ManagerAddress) and e_addr.funit:
            return e_addr.funit_type
        else:
            return '<unknown command>'

    def data(self, rec_value) -> variables.Variable:
        _value = rec_value if self._value == self.ANY_VALUE else self._value
        if isinstance(self._topic, (TopicCommandTros3, TopicStateTros3)):
            e_addr = self._topic.entity_addr
            var = variables.VariableTRS3(id=int(e_addr.enginery_id), cl=int(e_addr.funit_id), val=_value)
        elif isinstance(self._topic, (TopicCommand, TopicState)):
            e_addr = self._topic.entity_addr
            if isinstance(e_addr, (SubgineryAddress, EngineryAddress)):
                funit_id = e_addr.funit_id
            elif isinstance(e_addr, ManagerAddress) and e_addr.funit:
                funit_id = e_addr.funit[variables.ID]
            else:
                raise HandlingError(f'Can`t get funit_id')
            var = variables.VariableJocket.create_data(id=int(e_addr.entity_id), cl=funit_id, action=variables.SET, val=_value, key='ByScheduler')
        else:
            raise HandlingError(f'Topic {self._topic} is not Command-topic')

        return var

    def execute(self, handler, rec_value, condition_checker=None):
        if self._condition:
            if condition_checker(self._condition.topic) != self._condition.value:
                return
        handler(self._topic, self.data(rec_value), self.is_retained)
        if self.delay > 0:
            time.sleep(self.delay/1000)


class ScenarioAction(Action):
    TYPE = const.SCENARIO_TYPE

    def __init__(self, *args, **kwargs):
        super(ScenarioAction, self).__init__(*args, **kwargs)
        file_path = kwargs[const.FILE]
        self.file = file_path
        self.actions = []

        if os.path.isfile(file_path):
            with open(self.file, 'r') as file:
                data = file.read()
            if not data:
                data = '[]'
            data = json.loads(data)
            for action_data in data:
                action = action_of_data(action_data)
                self.actions.append(action)
        else:
            raise HandlingError(f'Scenarios file "{self.file}" not exist!')

    def __str__(self):
        return f'Scenario of "{self.file}"'

    @property
    def conditioned(self):
        for action in self.actions:
            if action.conditioned:
                return True
        return False

    @property
    def conditions(self):
        return [action._condition for action in self.actions if action._condition is not None]

    def execute(self, *args):
        for action in self.actions:
            action.execute(*args)


def action_of_data(data) -> Action:
    def separator(subclass): return issubclass(subclass, Action) and subclass.TYPE == data[const.TYPE]
    action_class = utils.get_subclass(Action, separator=separator)
    return action_class(**data)
