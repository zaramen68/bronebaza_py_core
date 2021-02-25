import datetime
import json

import spread_core.bam.schedule.const as const
from spread_core import mqtt
from spread_core.errors.project_errors import HandlingError, InitError
from spread_core.mqtt.variables import Variable
from spread_core.tools import utils

CALENDAR_PATH = ''

WORKDAYS_TYPE = 'workdays'
WEEKENDS_TYPE = 'weekends'

SUNDAY = 'Su'
MONDAY = 'Mo'
TUESDAY = 'Tu'
WEDNESDAY = 'We'
THURSDAY = 'Th'
FRIDAY = 'Fr'
SATURDAY = 'Sa'

WORKDAYS = [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY]
WEEKENDS = [SATURDAY, SUNDAY]
WEEK = WORKDAYS + WEEKENDS


def generate_holidays():
    today = datetime.datetime.now().date()
    result = []

    if CALENDAR_PATH == '':
        raise BaseException('Calendar path is not set!')
    with open(CALENDAR_PATH, 'r') as file:
        data = file.read()
    data = json.loads(data)
    for date_str in data:
        _date = datetime.date.fromisoformat(date_str)
        if _date >= today:
            result.append(_date)

    result.sort()

    return result


class Trigger:
    TYPE = None

    def __init__(self, *args, **kwargs):
        pass

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.TYPE == other.TYPE

    def __hash__(self):
        return hash(self.__str__())


class _AnyValue:
    def __eq__(self, other):
        return True


class _RangeValue:
    def __init__(self, ranges: str):
        self.ranges = []
        try:
            for i in ranges.split(','):
                i = i.strip()
                bounds = i.split('-')
                self.ranges.append(range(int(bounds[0]), int(bounds[1])))
        except BaseException as ex:
            raise InitError(f'Ошибка парсинга {self.__class__.__name__} для {ranges}: {ex}')

    def __eq__(self, other):
        for _range in self.ranges:
            if other in _range:
                return True

        return False


class _ListValue:
    def __init__(self, items: str):
        try:
            self.items = []
            for i in items.split(','):
                i = i.strip()
                if i.isdigit():
                    i = int(i)
                self.items.append(i)
        except BaseException as ex:
            raise InitError(f'Ошибка парсинга {self.__class__.__name__} для {items}: {ex}')

    def __eq__(self, other):
        return other in self.items


class BrokerTrigger(Trigger):
    TYPE = 'broker'
    ANY_VALUE = '#any'
    RANGE_VALUE = '#range('
    LIST_VALUE = '#list('

    def __init__(self, *args, **kwargs):
        super(BrokerTrigger, self).__init__(*args, **kwargs)
        self._topic = mqtt.of(kwargs[const.TOPIC])
        _value = kwargs[const.VALUE]
        if isinstance(_value, str) and _value == self.ANY_VALUE:
            self._value = _AnyValue()
        elif isinstance(_value, str) and _value.endswith(')') and _value.startswith(self.RANGE_VALUE):
            self._value = _RangeValue(_value[len(self.RANGE_VALUE):-1])
        elif isinstance(_value, str) and _value.endswith(')') and _value.startswith(self.LIST_VALUE):
            self._value = _ListValue(_value[len(self.LIST_VALUE):-1])
        else:
            self._value = _value

    def __str__(self):
        return f'{self._topic} as {self._value}'

    def check(self, topic: str, variable: Variable):
        if str(topic) == str(self._topic):
            if variable.value == self._value:
                return True

        return False

    @property
    def topic(self) -> mqtt.data.TopicData: return self._topic

    @property
    def value(self): return self._value


class DateTrigger(Trigger):
    ID = 0

    def __init__(self, *args, **kwargs):
        super(DateTrigger, self).__init__(*args, **kwargs)
        self.time = datetime.time.fromisoformat(kwargs[const.TIME])

    @property
    def is_ready(self):
        return False

    @property
    def has_next(self):
        return False

    @property
    def time_left(self):
        return 1

    def __str__(self):
        return f'{self.days if isinstance(self, WeekDays) else self.TYPE} at {self.time}'

    def __eq__(self, other):
        return super(DateTrigger, self).__eq__(other) and self.time == other.time

    def __cmp__(self, other):
        return self.time_left - other.time_left

    def __lt__(self, other):
        return self.time_left < other.time_left

    def __hash__(self):
        return 100000 * self.ID + self.time.second + 60*self.time.minute + 24*self.time.hour


class WeekDays(DateTrigger):
    ID = 1
    TYPE = 'weekdays'

    def __init__(self, *args, **kwargs):
        super(WeekDays, self).__init__(*args, **kwargs)
        days = kwargs[const.DAYS]
        self.days = []
        if len(days) == 0:
            raise HandlingError(f'{const.DAYS} expected 1..7 items')
        for day in days:
            if day in WEEK:
                self.days.append(day)
            else:
                raise HandlingError(f'{day} not include in standard values {WEEK}')

    @property
    def has_next(self):
        return True

    @property
    def time_left(self):
        now = datetime.datetime.now()
        days = []
        for day in self.days:
            index = WEEK.index(day)
            if index == now.weekday() and self.time > now.time():
                delta = 0
            elif index > now.weekday() or (index == now.weekday() and self.time > now.time()):
                delta = index - now.weekday()
            else:
                delta = 7 - now.weekday() + index
            _date = (now + datetime.timedelta(days=delta)).date()
            t = datetime.datetime.fromisoformat(str(_date) + ' ' + str(self.time))
            days.append(t)

        days.sort()

        target_time = days[0].timestamp()
        return int(target_time - now.timestamp())


class Holiday(DateTrigger):
    ID = 3
    TYPE = 'holiday'
    _days = None

    @staticmethod
    def days():
        if Holiday._days is None:
            Holiday._days = generate_holidays()
        return Holiday._days

    @property
    def has_next(self):
        return True

    @property
    def time_left(self):
        now = datetime.datetime.now()

        days = self.days().copy()

        while len(days) > 0:
            if days[0] < now.date() or (days[0] == now.date() and now.time() > self.time):
                days.pop(0)
            else:
                break

        if len(days) > 0:
            _date = days[0]
        else:
            raise HandlingError('calendar is empty!')

        target_time = datetime.datetime.fromisoformat(str(_date) + ' ' + str(self.time))
        return int(target_time.timestamp() - now.timestamp())


class WorkDays(DateTrigger):
    ID = 2
    TYPE = 'workday'

    @property
    def has_next(self):
        return True

    @property
    def time_left(self):
        now = datetime.datetime.now()

        _date = now.date()

        if _date not in Holiday.days():
            if self.time <= now.time():
                _date += datetime.timedelta(days=1)

        while _date in Holiday.days():
            _date += datetime.timedelta(days=1)

        target_time = datetime.datetime.fromisoformat(str(_date) + ' ' + str(self.time))
        return int((target_time - now).total_seconds())


def date_trigger_of_data(_type: str, data: dict) -> DateTrigger:
    for cl in DateTrigger.__subclasses__():
        if issubclass(cl, DateTrigger):
            if cl.TYPE == _type:
                return cl(**data)


def of(data: dict) -> Trigger:
    def separator(subclass): return issubclass(subclass, Trigger) and subclass.TYPE == data[const.TYPE]
    trigger_class = utils.get_subclass(Trigger, separator=separator)
    return trigger_class(**data)
