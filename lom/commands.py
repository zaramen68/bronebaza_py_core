import math
from datetime import datetime

from spread_core.tools import utils
from . import profiles
from .const import *


class LFrame:
    _cmd_id = None
    _address = None
    _fport = 1

    def __init__(self, dev_eui, pack=[]):
        """
        :param dev_eui: str - Идентификатор контроллера
        :param pack: bytes
        """
        self.dev_eui = dev_eui
        if len(pack) > 0:
            self.__cmd_id = pack[0]
        else:
            self.__cmd_id = None
        self._pack = list(pack[1:])

    def __str__(self):
        if len(self.pack) == 0 or self.__cmd_id is None:
            data = '<empty frame>'
        elif self._cmd_id is None:
            data = self.__cmd_id
        else:
            data = ' '.join(str(i) for i in self.pack)
        return '{0}(<{1}>): {2}'.format(self.__class__.__name__, self.dev_eui, data)

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        return isinstance(other, LFrame) and self.__class__ == other.__class__ and self.dev_eui == other.dev_eui and self.pack == other.pack

    pack = property(fget=lambda self: [self._cmd_id] + self._pack)
    fport = property(fget=lambda self: self._fport)


class LCommand(LFrame):

    @staticmethod
    def frame_to_data(pack):
        return pack[1:]

    def split(self, max_length: int):
        return [self]


class SetConfig(LCommand):
    """Команды конфигурации устройства в соответствии

    :param dev_eui: идентификатор контроллера
    :param _items: пары значений:
                conf_id - идентификатор параметра конфигурации
                value - значение параметра конфигурации
    """
    _cmd_id = 1
    items = property(fget=lambda self: self._pack)

    def __init__(self, dev_eui, *_items: list):
        req_data = []
        try:
            for funit_type, val in _items:
                if funit_type in CONFIGURATION:
                    item = CONFIGURATION[funit_type]
                    if FIELD_VARIANTS in item:
                        val = item[FIELD_VARIANTS].index(val)
                    elif FIELD_FORMAT in item:
                        fstr = item[FIELD_FORMAT].replace('{}', '')
                        val = val.replace(fstr, '')
                    elif FIELD_STATE in item:
                        val = int(val)
                    elif FIELD_MULTIPLIER in item:
                        val = val * item[FIELD_MULTIPLIER]
                    req_data.append([item[FIELD_ID], int(val)])
                else:
                    req_data.append([int(funit_type), int(val)])
        except BaseException as ex:
            raise ValueError('Parameters error: {0}'.format(ex))

        super(SetConfig, self).__init__(dev_eui, [self._cmd_id, *req_data])


class SetProfile(LCommand):
    """
    :param dev_eui: идентификатор контроллера
    :param profile: объект DimmingProfile или pack
    """

    _profile_class = None

    def __init__(self, dev_eui: str, *profile: (list, profiles.DimmingProfile)):
        if isinstance(profile[0], profiles.DimmingProfile):
            self.profile = profile
            profile = profile[0].pack
        else:
            self.profile = self._profile_class(*profile)

        super(SetProfile, self).__init__(dev_eui, [self._cmd_id, *profile])

    @classmethod
    def of(cls, dev_eui: str, profile: profiles.DimmingProfile):
        res = utils.get_subclass(cls, lambda scl: issubclass(scl, cls) and scl._profile_class == profile.__class__)
        return res(dev_eui, profile)

    def split(self, max_length: int):
        if len(self.pack[3:]) <= 2:
            return super(SetProfile, self).split(max_length)

        res = [self.__class__(self.dev_eui, *self.pack[1:5])]
        pack = self.pack[5:]
        for i in range(0, math.ceil(len(pack) / 5)):
            res.append(self.__class__(self.dev_eui, *list(self.pack[1:3] + pack[5*i:5+5*i])))
        return res


class SetGlobalGeoProfile(SetProfile):
    """Добавление/изменение записей в глобальном профиле диммирования на основе координат места установки"""
    _cmd_id = 2
    _profile_class = profiles.GlobalGeoProfile


class SetGlobalLumProfile(SetProfile):
    """Добавление/изменение записей в глобальном профиле диммирования на основе уровня освещенности"""
    _cmd_id = 3
    _profile_class = profiles.GlobalLumProfile


class SetPersonalGeoProfile(SetProfile):
    """Добавление/изменение записей в персональном профиле диммирования на основе координат места установки"""
    _cmd_id = 4
    _profile_class = profiles.PersonalGeoProfile


class SetPersonalLumProfile(SetProfile):
    """Добавление/изменение записей в персональном профиле диммирования на основе уровня освещенности"""
    _cmd_id = 5
    _profile_class = profiles.PersonalLumProfile


class SetGlobalUTCProfile(SetProfile):
    """Добавление/изменение записей в глобальном профиле диммирования на основе абсолютного времени"""
    _cmd_id = 6
    _profile_class = profiles.GlobalUTCProfile


class SetPersonalUTCProfile(SetProfile):
    """Добавление/изменение записей в персональный профиль диммирования на основе абсолютного времени"""
    _cmd_id = 7
    _profile_class = profiles.PersonalUTCProfile


class RemoveProfileItem(LCommand):
    """Удаление записей из профиля диммирования

    :param dev_eui: идентификатор контроллера
    :param _profile_id: идентификатор профиля
    :param _items: идентификаторы записей в профиле, которые подлежат удалению
    """

    _cmd_id = 8
    profile_id = property(fget=lambda self: self.pack[0])
    items = property(fget=lambda self: self.pack[1])

    def __init__(self, dev_eui, _profile_id, _items: list):
        super(RemoveProfileItem, self).__init__(dev_eui, [self._cmd_id, int(_profile_id), list(_items)])


class GlobalTimedLevel(SetProfile):
    """Команда установки глобального уровня диммирования на N секунд"""
    _cmd_id = 9
    _profile_class = profiles.GlobalTimedLevel


class ScanLine(LCommand):
    """Команда сканирования линии DALI"""
    _cmd_id = 12


class PersonalTimedLevel(SetProfile):
    """Команда установки персонального уровня диммирования на N секунд"""
    _cmd_id = 21
    _profile_class = profiles.PersonalTimedLevel


class ClearProfile(LCommand):
    """Очистка/удаление профиля диммирования

    При получении данной команды устройство должно удалить все записи из профиля диммирования,
    т.о. профиль перестает существовать. Если указанный профиль является глобальным и активным в настоящий момент,
    то устройство должно перейти на использование профиля 0

    :param dev_eui: идентификатор контроллера
    :param ids: идентификаторы профиля
    """
    _cmd_id = 10

    def __init__(self, dev_eui, ids: list):
        try:
            super(ClearProfile, self).__init__(dev_eui, [self._cmd_id, [int(i) for i in ids]])
        except:
            raise ValueError("profile_id required as int")

    ids = property(fget=lambda self: self._pack[0])


class SetActiveProfile(LCommand):
    """Команда установки активного глобального профиля диммирования

    :param dev_eui: идентификатор контроллера
    :param _id: идентификатор профиля
    """
    _cmd_id = 20
    id = property(fget=lambda self: self.pack[0])

    def __init__(self, dev_eui, _id: int):
        try:
            super(SetActiveProfile, self).__init__(dev_eui, [self._cmd_id, int(_id)])
        except:
            raise ValueError("profile_id required as int")


class ExtendLine(LCommand):
    """Расширение линии DALI"""
    _cmd_id = 25


class GetProfileId(LCommand):
    """Запрос текущего активного глобального профиля"""
    _cmd_id = 26


class GetConfig(LCommand):
    """Запрос текущей конфигурации устройства

    :param dev_eui: идентификатор контроллера
    :param _items: идентификаторы параметра конфигурации
    """
    _cmd_id = 27

    def __init__(self, dev_eui, _items: list):
        try:
            items = [CONFIGURATION[i][FIELD_ID] if i in CONFIGURATION else int(i) for i in _items]
            super(GetConfig, self).__init__(dev_eui, [self._cmd_id, items])
        except BaseException as ex:
            raise ValueError('Bad parameter: {0}'.format(ex))

    def split(self, max_length: int):
        res = []
        for i in range(0, math.ceil(len(self.pack[1]) / 5)):
            res.append(GetConfig(self.dev_eui, self.pack[1][i * 5:(i + 1) * 5]))

        return res


class ClearAllProfiles(LCommand):
    """Полная очистка всех профилей"""
    _cmd_id = 99


"""Answers
 https://docs.google.com/document/d/18l70dzPSCUIDfsLIdP_LjyV6RtVBtqlP2eaA_djga4k/edit#heading=h.zf2tqqun8v7x"""


class LAnswer(LFrame):
    _funit_type = []

    def __init__(self, dev_eui, pack):
        self._cmd_id = pack[0]
        super(LAnswer, self).__init__(dev_eui, pack)

    @property
    def success(self):
        return self._pack[0] == 1

    def __str__(self):
        if self.__class__ == LAnswer:
            cl = utils.get_subclass(LCommand, lambda sc: issubclass(sc, LCommand) and sc._cmd_id == self._cmd_id)
            name = cl.__name__ if cl else self.__class__.__name__
            return '{0}<{1}>: {2} {3}'.format(name, self.dev_eui, "SUCCESS" if self.success else "FAILED", self.pack)
        else:
            return super(LAnswer, self).__str__()

    @property
    def value(self):
        return {self._funit_type[i]: self._pack[i] for i in range(len(self._pack))}


class ScanResponse(LAnswer):
    """Результат сканирования линии DALI"""
    _cmd_id = 12
    _funit_type = [SCAN]


class ProfileResponse(LAnswer):
    """Ответ на запрос текущего активного профиля

    Данная команда передаются на FPort = 1. Ответ должен быть отправлен в случайный тайм слот.
    """
    _funit_type = [ACTIVE_PROFILE]
    _cmd_id = 26


class ConfResponse(LAnswer):
    """Ответ на запрос текущей конфигурации устройства
    """
    _cmd_id = 27
    _funit_type = list(CONFIGURATION.keys())

    @staticmethod
    def from_map(conf_id):
        for key, item in CONFIGURATION.items():
            if item[FIELD_ID] == conf_id:
                return key, item

        return None

    @property
    def value(self):
        conf = {}
        for c_id, val in self._pack:
            funit_type, item = self.from_map(c_id)
            if funit_type is not None:
                if funit_type == FIRMWARE:
                    val = '{0}.{1}'.format(val >> 4, val & 0xF)
                elif funit_type == MC_ADDRESS_GROUP1:
                    val = hex(val)[2:].upper().rjust(8, '0')
                elif funit_type == USER_PASS:
                    val = val.to_bytes(4, 'little').decode()
                elif funit_type == DEV_EUI:
                    val = hex(int.from_bytes(int(val).to_bytes(8, 'little'), 'big'))[2:].rjust(16, '0').upper()
                elif FIELD_VARIANTS in item:
                    val = item[FIELD_VARIANTS][val]
                elif FIELD_FORMAT in item:
                    val = item[FIELD_FORMAT].format(val)
                elif FIELD_STATE in item:
                    val = item[FIELD_STATE](val)
                elif FIELD_MULTIPLIER in item:
                    val = val / item[FIELD_MULTIPLIER]

                conf[funit_type] = val

        return conf
        # return {self._funit_type[0]: conf}


class ConfCommit(LAnswer):
    _cmd_id = 28


"""Events https://docs.google.com/document/d/18l70dzPSCUIDfsLIdP_LjyV6RtVBtqlP2eaA_djga4k/edit#heading=h.qr2wbqi6qkhm"""


class LEvent(LFrame):
    _fport = 2
    _flags = []
    _funit_type = []

    def flags(self, byte: int) -> {}:
        return {self._flags[i]: bool(byte & 2**i) for i in range(len(self._flags))}

    @property
    def value(self):
        return {self._funit_type[i]: self._pack[i] for i in range(len(self._pack))}


class LomStatusOrdinary(LEvent):
    """Очередной пакет данных

    Данная команда передаются на FPort = 2. Очередной пакет отправляется в случайный таймслот в рамках настройки
    DATA_TX_INTERVAL.
    """

    _cmd_id = 30
    _funit_type = [TIME, OPER_TIME, LATITUDE, LONGITUDE, ALTITUDE, ACTIVE_PROFILE, TEMP, TEMP_MIN, TEMP_MAX,
                   ILLUMINATION, TILT, FLAGS]
    _flags = ['Powered', 'Activated']

    @property
    def value(self):
        result = super(LomStatusOrdinary, self).value
        result[TIME] = str(datetime.fromtimestamp(self._pack[0])).replace(' ', 'T')
        result[LATITUDE] = self._pack[2] / 100000
        result[LONGITUDE] = self._pack[3] / 100000
        result[FLAGS] = self.flags(self._pack[11])
        return result


class LomStatusExtra(LEvent):
    """Внеочередной пакет данных

    Данная команда передаются на FPort = 2.
    В зависимости от ситуации, может отправляться как немедленно, так и в случайный таймслот.
    В ситуациях, когда в результате возникновения какой-либо проблемы, для которой генерируется внеочередной
    пакет, могут случиться коллизии, должен использоваться механизм отложенной доставки. Например: отключение питания.
    В противном случае пакет должен генерироваться и отправляться немедленно.
    Например: изменение наклона выше критического уровня.
    """

    _cmd_id = 31
    _funit_type = [TIME, OPER_TIME, ACTIVE_PROFILE, TEMP, ILLUMINATION, TILT, EXTRA_FLAGS]
    _flags = ['PowerFail', 'PowerRestored', 'HighTilt', 'Shock']

    @property
    def value(self):
        result = super(LomStatusExtra, self).value
        result[TIME] = str(datetime.fromtimestamp(self._pack[0])).replace(' ', 'T')
        result[EXTRA_FLAGS] = self.flags(self._pack[6])
        return result


class DaliStatus(LEvent):
    """Выявлены проблемы при сканировании статусов устройств сети DALI

    Данная команда передаются на FPort = 3.
    Внеочередной пакет отправляемый немедленно по факту выявления проблем в светильниках, подключенных к шине DALI.
    Пакет передается только в том случае, если битовые поля Lamp Failure, Limit Error, Power Failure установлены в 1.
    """
    _cmd_id = 32
    _fport = 3
    _funit_type = [DALI_STATUS]
    _flags = ['ControlGear', 'LampFailure', 'LightOn', 'LimitError', 'FadeRunning', 'ResetState', 'MissingSA', 'PowerFailure']

    def value(self):
        return {self._pack[2*n]: self.flags(self._pack[0]) for n in range(int(len(self._pack)/2))}


def event_of(dev_eui, pack):
    if len(pack) > 0:
        for sc in LEvent.__subclasses__():
            if issubclass(sc, LEvent) and sc._cmd_id == pack[0]:
                return sc(dev_eui, pack)

    return LEvent(dev_eui, pack)


def request_of(dev_eui, pack):
    if len(pack) > 0:
        res = utils.get_subclass(LCommand, lambda sc: issubclass(sc, LCommand) and sc._cmd_id == pack[0])
        if res:
            return res(dev_eui, *res.frame_to_data(pack))

    return LCommand(dev_eui, pack)


def response_of(dev_eui, pack):
    if len(pack) > 0:
        for sc in LAnswer.__subclasses__():
            if issubclass(sc, LAnswer) and sc._cmd_id == pack[0]:
                return sc(dev_eui, pack)

    return LAnswer(dev_eui, pack)
