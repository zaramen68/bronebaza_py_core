from spread_core.bam.schedule.tasks import task_of_data


class Location:
    def __init__(self, _id: int = None, _enabled: bool = False, _name='', _tasks=[]):
        self._id = _id
        self.enabled = _enabled
        self.name = _name
        self.tasks = _tasks if _tasks else []

    def get_id(self) -> int: return self._id
    def set_id(self, _id: int): self._id = _id

    id = property(fget=get_id, fset=set_id, doc='id')

    def __str__(self):
        return f'{self.name if self.name else self.__class__.__name__}({self.id}){ "DISABLED" if not self.enabled else ""}'

    def __repr__(self):
        return self.__str__()

    def __hash__(self):
        return self.id

    def __eq__(self, other):
        return other.id == self.id


def location_of_data(data: dict) -> Location:
    location = Location(_id=data['locationID'], _enabled=data['enabled'])
    if 'name' in data:
        location.name = data['name']
    if 'tasks' in data and isinstance(data['tasks'], list):
        for task_data in data['tasks']:
            if 'type' in task_data and 'triggers' in task_data and isinstance(task_data['triggers'], list):
                for trigger_data in task_data['triggers']:
                    task = task_of_data(location, task_data['type'], trigger_data)
                    location.tasks.append(task)

    return location
