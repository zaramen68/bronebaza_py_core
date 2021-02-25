from spread_core.bam.handling.actions import action_of_data
from spread_core.bam.handling.triggers import DateTrigger, date_trigger_of_data


class Task:
    def __init__(self, location, _trigger: DateTrigger = None, _actions=None):
        self.location = location
        self.trigger = _trigger
        self.actions = _actions if _actions else []

    def __str__(self):
        return '{0} <{1} actions by {2}> of {3}'.format(self.__class__.__name__, len(self.actions), self.trigger, self.location)

    def __repr__(self):
        return self.__str__()


def task_of_data(location, _type: str, data: dict) -> Task:
    task = Task(location)
    task.trigger = date_trigger_of_data(_type, data)
    for action_data in data['actions']:
        action = action_of_data(action_data)
        task.actions.append(action)

    return task
