import datetime

from astral import sun, Observer


class DimmingItem:
    def __init__(self, *args: int):
        self._pack = list(args)

    pack = property(fget=lambda self: self._pack)
    id = property(fget=lambda self: int(self._pack[0]))
    value = property(fget=lambda self: int(self._pack[-1]))

    def __str__(self): return f'{self.__class__.__name__}: {self.pack}'

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        return other.__class__ == self.__class__ and self.pack == other.pack

    @property
    def time_left(self):
        raise NotImplementedError()

    def serialize(self) -> dict:
        raise NotImplementedError()

    @staticmethod
    def deserialize(data):
        raise NotImplementedError()


class LumItem(DimmingItem):
    """
    Запись профиля диммирования на основе уровня освещенности

    :param _id - идентификатор записи в профиле
    :param _illumination - уровень освещенности в процентах 0-100
    :param _value - уровень диммирования (0-254) или номер сцены (1-16) в зависимости от PROFILE_TYPE
    """

    def __init__(self, _id: int, _illumination: int, _value: int):
        try:
            _id = int(_id)
            _illumination = int(_illumination)
            _value = int(_value)
        except:
            raise ValueError("parameters required as int")

        if not 0 <= _illumination <= 100:
            raise ValueError("illumination value required in 0..100")

        if not 0 <= _value <= 0xfe:
            raise ValueError("value value required in 0..254")

        DimmingItem.__init__(self, _id, _illumination, _value)

    lum = property(fget=lambda self: int(self._pack[1]))

    def __str__(self):
        return f'{self.__class__.__name__}<{self.id}>: set {self.value} at {self.lum}%'

    @property
    def time_left(self):
        return 0xffffffff

    def serialize(self) -> dict:
        return dict(id=self.id, lum=self.lum, value=self.value)

    @staticmethod
    def deserialize(data):
        return LumItem(int(data['id']), int(data['lum']), int(data['value']))


class UTCItem(DimmingItem):
    """
    Запись профиля диммирования на основе абсолютного времени

    :param _id - идентификатор записи в профиле
    :param _hours - часы 0-23
    :param _minutes - минуты 0- 59
    :param _value - уровень диммирования (0-254) или номер сцены (1-16) в зависимости от PROFILE_TYPE
    """

    def __init__(self, _id: int, _hours: int, _minutes: int, _value: int):
        try:
            _id = int(_id)
            _hours = int(_hours)
            _minutes = int(_minutes)
            _value = int(_value)
        except:
            raise ValueError("parameters required as int")

        if not 0 <= _hours <= 23:
            raise ValueError("hours value required in 0..23")

        if not 0 <= _minutes <= 59:
            raise ValueError("hours value required in 0..59")

        if not 0 <= _value <= 0xfe:
            raise ValueError("value value required in 0..254")

        DimmingItem.__init__(self, _id, _hours, _minutes, _value)

        self._utc = datetime.time(hour=_hours, minute=_minutes, tzinfo=datetime.timezone.utc)

    hours = property(fget=lambda self: int(self._pack[1]))
    minutes = property(fget=lambda self: int(self._pack[2]))

    @property
    def time_left(self):
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        target = datetime.datetime(now.year, now.month, now.day, self._utc.hour, self._utc.minute, tzinfo=datetime.timezone.utc)
        diff = int((target - now).total_seconds())
        if diff <= 0:
            diff = 60*60*24 + diff
        return diff

    def __str__(self):
        return f'{self.__class__.__name__}<{self.id}>: ' \
            f'set {self.value} ' \
            f'at {datetime.time(hour=self.hours, minute=self.minutes)}(UTC)'

    def serialize(self) -> dict:
        return dict(id=self.id, hours=self.hours, minutes=self.minutes, value=self.value)

    @staticmethod
    def deserialize(data):
        return UTCItem(int(data['id']), int(data['hours']), int(data['minutes']), int(data['value']))


class GeoItem(DimmingItem):
    """
    Запись профиля диммирования на основе координат места установки

    :param _id: идентификатор записи в профиле
    :param _offset_type: тип смещения: 0 - от заката; 1 - от восхода.
    :param _offset_value: смещение в секундах, может быть отрицательным
    :param _value: уровень диммирования (0-254) или номер сцены (1-16) в зависимости от PROFILE_TYPE
    """

    SUNSET = 0
    SUNRISE = 1
    LAST_TYPE = SUNRISE
    TYPES = ['Sunset', 'Sunrise', 'UTC']

    @classmethod
    def of_sunset(cls, id: int, offset: int, value: int):
        return cls(id, cls.SUNSET, offset, value)

    @classmethod
    def of_sunrise(cls, id: int, offset: int, value: int):
        return cls(id, cls.SUNRISE, offset, value)

    def __init__(self, _id: int, _offset_type: int, _offset_value: int, _value: int):
        self._position = None
        try:
            _id = int(_id)
            _offset_type = int(_offset_type)
            _offset_value = int(_offset_value)
            _value = int(_value)
        except:
            raise ValueError("parameters required as int")

        if not 0 <= _offset_type <= self.LAST_TYPE:
            raise ValueError("offset_type value required as 0 for sunset or 1 for sunrise")

        if not 0 <= _value <= 0xfe:
            raise ValueError("value value required in 0..254")

        DimmingItem.__init__(self, _id, _offset_type, _offset_value, _value)

    offset_type = property(fget=lambda self: int(self._pack[1]))
    offset_value = property(fget=lambda self: int(self._pack[2]))

    def set_position(self, latitude: float, longitude: float, altitude: float = 0.0):
        self._position = (latitude, longitude, altitude)

    def __str__(self):
        return f'{self.__class__.__name__}<{self.id}>: ' \
            f'set {self.value} ' \
            f'at {"sunset" if self.offset_type == 0 else "sunrise"} ' \
            f'{"+" if self.offset_value > 0 else "-"} {datetime.timedelta(seconds=abs(self.offset_value))}'

    @property
    def time_left(self):
        if self._position:
            sun = Sun.near(self.offset_value, *self._position)
            if self.offset_type == self.SUNRISE:
                target = int((sun.sunrise - datetime.datetime.now(datetime.timezone.utc)).total_seconds()) + 1
            else:
                target = int((sun.sunset - datetime.datetime.now(datetime.timezone.utc)).total_seconds()) + 1
            return target + self.offset_value

        raise AttributeError('Position is not set!')

    def serialize(self) -> dict:
        return dict(id=self.id, type=self.TYPES[self.offset_type], offset=self.offset_value, value=self.value)

    @staticmethod
    def deserialize(data):
        return GeoItem(int(data['id']), GeoItem.TYPES.index(data['type']), int(data['offset']), int(data['value']))


class GlobalGeoItem(GeoItem, UTCItem):
    FIX_TIME = 2
    LAST_TYPE = FIX_TIME
    TYPES = ['Sunset', 'Sunrise', 'UTC']

    """
    Запись глобального профиля диммирования на основе координат места установки

    :param _id: идентификатор записи в профиле
    :param _offset_type: тип смещения: 0 - от заката; 1 - от восхода, 2 - фиксированное время.
    :param _offset_value: смещение в секундах (только для OFFSET_TYPE 0 или 1), может быть отрицательным
    :param _hours - часы 0-23 (только для OFFSET_TYPE=2)
    :param _minutes - минуты 0- 59 (только для OFFSET_TYPE=2)
    :param _value: уровень диммирования (0-254) или номер сцены (1-16) в зависимости от PROFILE_TYPE
    """

    @classmethod
    def of_fix_time(cls, id: int, hours: int, minutes: int, value: int):
        return cls(id, cls.FIX_TIME, hours, minutes, value)

    def __init__(self, *_args):
        _args = list(_args)
        try:
            args = [int(a) for a in list(_args)]
        except:
            raise ValueError("parameters required as int")

        self._offset_type = args[1]

        if args[1] == self.FIX_TIME:
            UTCItem.__init__(self, args[0], _hours=args[2], _minutes=args[3], _value=args[4])
        else:
            GeoItem.__init__(self, args[0], _offset_type=args[1], _offset_value=args[2], _value=args[3])

    offset_type = property(fget=lambda self: self._offset_type)
    pack = property(fget=lambda self: [self.id, self.offset_type] + self._pack[1:] if self.offset_type == self.FIX_TIME else self._pack)

    @property
    def time_left(self):
        if self.offset_type == self.FIX_TIME:
            return super(GeoItem, self).time_left
        return super(GlobalGeoItem, self).time_left

    def __str__(self):
        if self.offset_type == self.FIX_TIME:
            return UTCItem.__str__(self)
        return GeoItem.__str__(self)

    def serialize(self) -> dict:
        res = dict(type=self.TYPES[self.offset_type], value=self.value)
        if self.offset_type == self.FIX_TIME:
            res.update(UTCItem.serialize(self))
        else:
            res.update(GeoItem.serialize(self))

        return res

    @staticmethod
    def deserialize(data):
        _type = GlobalGeoItem.TYPES.index(data['type'])
        args = int(data['id']), _type
        if args[1] == GlobalGeoItem.FIX_TIME:
            args += int(data['hours']), int(data['minutes']), int(data['value'])
        else:
            args += int(data['offset']), int(data['value'])

        return GlobalGeoItem(*args)


class TimedLevel(DimmingItem):
    """Запись глобального профиля диммирования на N секунд

    :param _value: уровень диммирования (0-254))
    :param _period: время действия команды в секундах, если 0, то действует бесконечно
    """

    id = 0
    value = property(fget=lambda self: int(self._pack[-2]))
    period = property(fget=lambda self: int(self._pack[-1]))

    def __init__(self, _value, _period):
        try:
            _value = int(_value)
            _period = int(_period)
        except:
            raise ValueError("parameters required as int")

        if not 0 <= _value <= 0xfe:
            raise ValueError("value value required in 0..254")

        if not 0 <= _period:
            raise ValueError("period required as positive number")

        super(TimedLevel, self).__init__(_value, _period)

    def __str__(self):
        return f'{self.__class__.__name__}: set {self.value} for {self.period} sec'

    @property
    def time_left(self):
        return 0

    def serialize(self) -> dict:
        return dict(value=self.value, period=self.period)

    @staticmethod
    def deserialize(data):
        return TimedLevel(data['value'], data['period'])


class TimedLevelAddressed(TimedLevel):
    """Запись персонального профиля диммирования на N секунд

    :param _address: короткий адрес устройства/SN - массив байтов серийного номера светильника(4 байта Lsb first)
    :param _value: уровень диммирования (0-254)
    :param _period: через какое время вернуться обратно к активному профилю, секунды (0 - не возвращаться)
    """

    address = property(fget=lambda self: int(self._pack[0]))

    def __init__(self, _address, _value, _period):
        try:
            _address = int(_address)
            if _value not in range(0, 64):
                raise ValueError("_value value required in 0..63")
        except:
            try:
                _address = [int(i) for i in list(_address)]
            except:
                raise ValueError("parameters required as int")

        if not 0 <= _value <= 0xfe:
            raise ValueError("value value required in 0..254")

        if not 0 <= _period:
            raise ValueError("period required as positive number")

        super(TimedLevel, self).__init__(_value, _period)
        self._pack.insert(0, _address)


class Sun:
    """Объект, предоставляющий время восхода и заката"""
    def __init__(self, sunrise, sunset):
        self._sunrise = sunrise
        self._sunset = sunset

    sunrise = property(fget=lambda self: self._sunrise)
    sunset = property(fget=lambda self: self._sunset)

    @classmethod
    def near(cls, offset: int, latitude: float, longitude: float, altitude: float = 0.0):
        """
        Объект, предоставляющий время ближайших(справа) восхода и заката
        :param latitude: широта
        :param longitude: долгота
        :param altitude: высота
        :return:
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        observer = Observer(latitude, longitude, altitude)
        tzinfo = datetime.timezone.utc

        s = sun.sun(observer, date=now.date(), tzinfo=tzinfo)
        sunrise = s['sunrise']
        sunset = s['sunset']

        if now > sunset or now > sunrise:
            s = sun.sun(observer, date=now.date() + datetime.timedelta(days=1), tzinfo=tzinfo)
            if now > sunset + datetime.timedelta(seconds=offset):
                sunset = s['sunset']
            if now > sunrise + datetime.timedelta(seconds=offset):
                sunrise = s['sunrise']

        return cls(sunrise, sunset)


# if __name__ == '__main__':
#     s = sun.sun(Observer(57.6299, 39.8737), date=datetime.date.today(), tzinfo=datetime.timezone.utc)
#     print((
#         f'Dawn:    {s["dawn"]}\n'
#         f'Sunrise: {s["sunrise"]}\n'
#         f'Noon:    {s["noon"]}\n'
#         f'Sunset:  {s["sunset"]}\n'
#         f'Dusk:    {s["dusk"]}\n'
#     ))
