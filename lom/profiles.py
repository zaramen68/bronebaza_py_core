import datetime
import json
import logging

from lom import profile_items
from spread_core.tools import utils

UNSET_POSITION = (0, 0, 0)


# [CMD_ID=2] global geo	CMD_ID, PROFILE_TYPE,	PROFILE_ID,			 [ID, OFFSET_TYPE, OFFSET_VALUE, DIMMING_LEVEL]
# [CMD_ID=3] global lum	CMD_ID, PROFILE_TYPE,	PROFILE_ID, 		 [ID, ILLUMINATION, DIMMING_LEVEL]
# [CMD_ID=4] person geo	CMD_ID,                 PROFILE_ID, SA/[SN], [ID, OFFSET_TYPE, OFFSET_VALUE, DIMMING_LEVEL]
# [CMD_ID=5] person lum	CMD_ID,                 PROFILE_ID, SA/[SN], [ID, ILLUMINATION, DIMMING_LEVEL]
# [CMD_ID=6] global tim	CMD_ID, PROFILE_TYPE,	PROFILE_ID, 		 [ID, HOURS, MINUTES, DIMMING_LEVEL]
# [CMD_ID=7] person tim	CMD_ID,                 PROFILE_ID, SA/[SN], [ID, HOURS, MINUTES, DIMMING_LEVEL]

class DimmingProfile:
    _items_index = 2
    _timed = False
    _items_class = profile_items.DimmingItem
    _type = None

    id = property(fget=lambda self: self.pack[1])
    is_timed = property(lambda self: self._timed)
    pack = property(lambda self: self._pack)

    def __init__(self, *_pack: (int, list)):
        self._position = UNSET_POSITION
        self._pack = list(_pack)

    def __str__(self):
        return f'{self.__class__.__name__}({self.id}): {" ".join(str(i) for i in self.pack)}'

    def __repr__(self): return self.__str__()

    def __eq__(self, other):
        return isinstance(other, DimmingProfile) and self.pack == other.pack

    @property
    def items(self):
        res = []
        for item_pack in self.pack[self._items_index:]:
            item = self._items_class(*item_pack)
            res.append(item)
            if isinstance(item, profile_items.GeoItem):
                item.set_position(*self._position)

        res.sort(key=lambda _item: _item.time_left)
        return res

    def add_item(self, item: profile_items.DimmingItem):
        self._pack.append(item.pack)
    
    @property
    def position(self):
        return self._position
    
    def set_position(self, latitude: float, longitude: float, altitude: float = 0.0):
        try:
            _pos = (float(latitude), float(longitude), float(altitude))
        except:
            raise BaseException('latitude, longitude and altitude required as float')
        else:
            has_changed = False
            has_changed = abs(self._position[0] - _pos[0]) > 0.5 or has_changed
            has_changed = abs(self._position[1] - _pos[1]) > 0.5 or has_changed
            has_changed = abs(self._position[2] - _pos[2]) > 50 or has_changed

            if has_changed:
                self._position = _pos

            return has_changed

    def serialize(self) -> dict: return {}


class GlobalDimmingProfile(DimmingProfile):
    """
    :param _type: тип профиля: 0 - с указанием уровня диммирования; 1 - с указанием номера DALI сцены.
    :param _id: идентификатор профиля
    :param _items: записи профиля
    """
    LEVEL_CONTROL = 0
    SCENE_CONTROL = 1
    TYPES = ['Level', 'Scene']
    operand = property(fget=lambda self: self._pack[0])

    def __init__(self, _type: int, _id: int, *_items: list):
        super(GlobalDimmingProfile, self).__init__(_type, _id, *_items)

    @classmethod
    def of_level(cls, _id: int, *_items: profile_items.DimmingItem) -> DimmingProfile:
        return cls(cls.LEVEL_CONTROL, _id, *[i.pack for i in _items])

    @classmethod
    def of_scene(cls, _id: int, *_items: profile_items.DimmingItem) -> DimmingProfile:
        return cls(cls.SCENE_CONTROL, _id, *[i.pack for i in _items])

    def serialize(self) -> dict:
        return dict(type=self._type, operand=self.TYPES[self.operand], id=self.id, items=[item.serialize() for item in self.items])

    @classmethod
    def deserialize(cls, data):
        _type = data['type']
        args = []
        if 'operand' in data:
            args.append(cls.TYPES.index(data['operand']))
        if 'id' in data:
            args.append(int(data.pop('id')))
        scl = utils.get_subclass(cls, lambda scl: issubclass(scl, cls) and scl._type == _type)
        args += [scl._items_class.deserialize(i).pack for i in data['items']]
        return scl(*args)


class PersonalDimmingProfile(DimmingProfile):
    """Добавление/изменение записей в персональном профиле диммирования

    :param dev_eui: идентификатор контроллера
    :param _id: идентификатор профиля
    :param _address: короткий адрес устройства/массив байтов серийного номера светильника (4 байта, LSB first)
    :param _items: записи профиля
    """

    _items_index = 3
    id = property(fget=lambda self: self.pack[0])
    address = property(fget=lambda self: self.pack[1])

    def __init__(self, _id: int, _address: (list, int), *_items: list):
        super(PersonalDimmingProfile, self).__init__(_id, _address, *_items)

    @classmethod
    def of_level(cls, _id: int, _address: (list, int), *items: profile_items.DimmingItem) -> DimmingProfile:
        return cls(_id, _address, *[item.pack for item in items])

    def serialize(self) -> dict:
        return dict(type=self._type, id=self.id, address=self.address, items=[item.serialize() for item in self.items])

    @classmethod
    def deserialize(cls, data):
        _type = data['type']
        args = [data['id'], data['address']]
        scl = utils.get_subclass(cls, lambda scl: issubclass(scl, cls) and scl._type == _type)
        args += [scl._items_class.deserialize(i).pack for i in data['items']]
        return scl(*args)


class UTCProfile(DimmingProfile):
    _type = 'UTC'
    _timed = True


class GlobalUTCProfile(UTCProfile, GlobalDimmingProfile):
    """Глобальный профиль диммирования на основе абсолютного времени"""
    _items_class = profile_items.UTCItem


class PersonalUTCProfile(UTCProfile, PersonalDimmingProfile):
    """Персональный профиль диммирования на основе абсолютного времени"""
    _items_class = profile_items.UTCItem


class LumProfile(DimmingProfile):
    _type = 'Lum'

    @property
    def items(self):
        res = super(LumProfile, self).items
        res.sort(key=lambda _item: _item.lum)
        return res


class GlobalLumProfile(LumProfile, GlobalDimmingProfile):
    """Глобальный профиль диммирования на основе уровня освещенности"""
    _items_class = profile_items.LumItem


class PersonalLumProfile(LumProfile, PersonalDimmingProfile):
    """Персональный профиль диммирования на основе уровня освещенности"""
    _items_class = profile_items.LumItem


class GeoProfile(DimmingProfile):
    _type = 'Geo'
    _timed = True


class GlobalGeoProfile(GeoProfile, GlobalDimmingProfile):
    """Глобальный профиль диммирования на основе координат места установки"""
    _items_class = profile_items.GlobalGeoItem

    @classmethod
    def default(cls):
        return cls.of_level(0, profile_items.GlobalGeoItem.of_sunrise(1, 0, 0), profile_items.GlobalGeoItem.of_sunset(2, 0, 254))


class PersonalGeoProfile(GeoProfile, PersonalDimmingProfile):
    """Персональный профиль диммирования на основе координат места установки"""
    _items_class = profile_items.GeoItem


class TimedLevelProfile(DimmingProfile):
    """
    :param dev_eui: идентификатор контроллера
    :param _items: записи профиля
    """
    _type = 'Temp'
    _items_index = 0
    id = -1

    def __init__(self, *pack: int):
        super(TimedLevelProfile, self).__init__(*pack)
        self.start_time = datetime.datetime.now(datetime.timezone.utc)

    @property
    def items(self):
        return [self._items_class(*self.pack)]

    @classmethod
    def of_level(cls, *_items: profile_items.DimmingItem) -> DimmingProfile:
        return cls(*[i.pack for i in _items])

    def serialize(self) -> dict:
        return dict(type=self._type, items=[dict(period=item.period, value=item.value) for item in self.items if isinstance(item, profile_items.TimedLevel)])


class GlobalTimedLevel(TimedLevelProfile, GlobalDimmingProfile):
    """Профиль глобального уровня диммирования на N секунд"""
    _items_class = profile_items.TimedLevel

    def __init__(self, *pack: list):
        if not isinstance(pack[0], int):
            pack = pack[0]
        TimedLevelProfile.__init__(self, *pack)

    @classmethod
    def of_level(cls, _item: profile_items.DimmingItem, **kwargs) -> DimmingProfile:
        return cls(_item.pack)

    @classmethod
    def of_scene(cls, *_items: profile_items.DimmingItem) -> DimmingProfile:
        raise NotImplemented()


class PersonalTimedLevel(TimedLevelProfile, PersonalDimmingProfile):
    """Профиль персонального уровня диммирования на N секунд"""
    _items_class = profile_items.TimedLevelAddressed


if __name__ == '__main__':
    stack = {}

    for args in [
        (PersonalUTCProfile, 1001, 111, profile_items.UTCItem(1, 23, 35, 10), profile_items.UTCItem(2, 18, 0, 100)),
        (PersonalLumProfile, 1002, 222, profile_items.LumItem(1, 20, 50), profile_items.LumItem(2, 50, 100)),
        (PersonalGeoProfile, 1003, 333, profile_items.GeoItem(1, 0, 3600, 100), profile_items.GeoItem(2, 1, 30, 200)),

        (GlobalGeoProfile, 1004, profile_items.GlobalGeoItem(1, 0, 3600, 100), profile_items.GlobalGeoItem(2, 2, 15, 00, 200)),
        (GlobalUTCProfile, 1005, profile_items.UTCItem(1, 18, 0, 10), profile_items.UTCItem(2, 10, 35, 100)),
        (GlobalLumProfile, 1006, profile_items.LumItem(1, 20, 50), profile_items.LumItem(2, 50, 100)),

        (PersonalTimedLevel, profile_items.TimedLevelAddressed([1, 2, 3], 50, 254), profile_items.TimedLevelAddressed(2, 0, 0)),
        (GlobalTimedLevel, profile_items.TimedLevel(20, 125)),
    ]:
        cls = args[0]
        assert issubclass(cls, (GlobalDimmingProfile, PersonalDimmingProfile))
        try:
            # print(cls.__name__.center(50, '-'))
            p = cls.of_level(*args[1:]).set_position(57.6299, 39.8737, 0)
            _if = p.id
            # print(str(p))
            items = p.items
            # for item in items:
                # print(f'    {item} {f"left {datetime.timedelta(seconds=item.time_left(*p._position))}" if not isinstance(item, profile_items.LumItem) else ""}')
            print(json.dumps(p.serialize()))#, indent=4))

            p2 = cls(*p.pack)
            # print('SUCCESS' if p.pack == p2.pack else 'FAILED')

            stack[p.id] = p.pack
        except BaseException as ex:
            logging.exception(ex)#f'{ex.__class__.__name__} {str(ex)}')

    # with open('/var/project/dump/profiles.yaml', 'w') as f:
    #     yaml.dump(stack, f)
