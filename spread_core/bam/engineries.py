from spread_core import mqtt
from spread_core.bam.dali import *
from spread_core.bam.dali.providers import lights
from spread_core.bam.entities import Entity
from spread_core.bam.recipe.recipe import Recipe
from spread_core.errors.project_errors import ProjectError, StateError, CommandError, JocketError
from spread_core.mqtt import TopicCommand, ProviderAddress, S_TYPE, TopicStateTros3, EngineryAddress, TopicState
from spread_core.mqtt.variables import VariableJocket, VariableTRS3
from spread_core.protocols.dali.command import CommandSignature
from spread_core.tools import settings

onId = 'onId'
offId = 'offId'
isOnId = 'isOnId'
setLevelId = 'setLevelId'
levelId = 'levelId'
groupOnId = 'groupOnId'
groupOffId = 'groupOffId'
groupSetLevelId = 'groupSetLevelId'
historyRequestId = 'historyRequestId'
historyResponseId = 'historyResponseId'
powerLevelId = 'powerLevelId'
setColorId = 'setColorId'
colorId = 'colorId'
lastLevelId = 'lastLevel'

LUMINOSITY_TYPE = 'Luminosity'
PRESENCE_TYPE = 'Presence'
ACTUATION_TYPE = 'Actuation'

ACTION_OFF = ''
ACTION_MIN_LEVEL = 'MinLevel'
ACTION_MAX_LEVEL = 'MaxLevel'
ACTION_LAST_LEVEL = 'LastLevel'
ACTION_LEVEL = 'Level'
ACTION_SCENE = 'Scene'


def of(p_id, data, manager_data):
    if data['type'] == SwitchingLight.__name__:
        return SwitchingLight(p_id, data, manager_data)
    elif data['type'] == DimmingLight.__name__:
        return DimmingLight(p_id, data, manager_data)
    elif data['type'] == RgbLight.__name__:
        return RgbLight(p_id, data, manager_data)
    elif data['type'] == DynamicLight.__name__:
        return DynamicLight(p_id, data, manager_data)
    elif data['type'] == LightSensor.__name__:
        return LightSensor(p_id, data, manager_data)
    elif data['type'] == PresenceSensor.__name__:
        return PresenceSensor(p_id, data, manager_data)
    elif data['type'] == LightingArea.__name__:
        return LightingArea(p_id, data, manager_data)
    else:
        raise ProjectError('Unknown enginery type', data=data)


class ManagerData:
    def __init__(self, data):
        self.id = data['id']
        self.s_type = S_TYPE
        self.m_type = data['type']
        self.s_id = data['serverID']


class Enginery(Entity):
    _provider_type = None
    _funit_type = None
    _group_funit_type = None
    _cmds = []

    def __init__(self, p_id,  data, manager_data):
        super(Enginery, self).__init__(data['id'])
        self._label = data['label']
        self._key = data['key']
        self._attributes = data['attributes'] if 'attributes' in data else dict()
        if manager_data:
            self.manager = ManagerData(manager_data)
        self._subgineries = []
        self._la = None
        self._recipe = None
        self.p_id = p_id

    @property
    def recipe(self) -> Recipe:
        return self._recipe

    def set_la(self, la):
        self._la = la

    def set_provider(self, recipe):
        self._recipe = recipe

    def set_subginery(self, subginery):
        if subginery not in self._subgineries:
            self._subgineries.append(subginery)

    def on_command(self, provider_id, topic, variable):
        val = self.generate_value(variable)
        if self._cmds[variable.cl] == groupSetLevelId \
                or self._cmds[variable.cl] == groupOnId \
                or self._cmds[variable.cl] == groupOffId:
            e_addr = self.get_provider_addr(self._group_funit_type)
        else:
            e_addr = self.get_provider_addr(self._funit_type)
        topic = TopicCommand(topic.p_id, session_id='LE_SID', entity_addr=e_addr)
        return topic, VariableJocket.create_data(id=provider_id, cl=e_addr.funit['id'], action='set', val=val)

    def on_command_j(self, project_id, funit_type, value):
        _p_addr = self.get_provider_addr(funit_type)
        topic = mqtt.TopicCommand(project_id, 'LE_SID', _p_addr)
        jocket = VariableJocket.create_data(id=_p_addr.provider_id, cl=_p_addr.funit['id'],
                                            val=value,
                                            action=mqtt.variables.SET)
        return topic, jocket

    def on_state(self, topic, jocket):
        raise StateError('State of {} not implemented for {}({})!'
                         .format(topic.entity_addr.funit_type, self.__class__.__name__, self.id))

    def generate_value(self, variable):
        raise CommandError('Impossible variable id', variable=str(variable))

    def get_address(self, funi_id):
        return EngineryAddress(self.id, funi_id)

    def get_provider_addr(self, funit_type):
        return ProviderAddress(self.manager.s_type, self.manager.s_id, self.manager.m_type, self.manager.id,
                               self.recipe.provider_type, self.recipe.id, funit_type)

    def publish_state(self, funit_type, value, invalid=False):
        self.set_value(funit_type, value)
        _addr = self.get_address(funit_type)
        if isinstance(self, LightingArea):
            funit = self.get_funit(funit_type)
            topic = TopicState(self.p_id, _addr)
            data = VariableJocket.create_data(id=self.id, cl=funit['id'], action=mqtt.variables.STATE, val=value, invalid=invalid)
        else:
            topic = TopicStateTros3(self.p_id, _addr)
            data = VariableTRS3(id=self.id, cl=funit_type, val=value, invalid=invalid)

        return topic, data

    def set_invalid(self):
        result = []
        for class_id in self.values:
            result.append(self.publish_state(class_id, value=self.get_value(class_id), invalid=True))
        return result


class Light(Enginery):
    _funit_type = BRIGHTNESS_LEVEL
    _group_funit_type = F_GROUP_LEVEL

    def __init__(self, *args):
        super(Light, self).__init__(*args)
        self.power = self._attributes['power'] if 'power' in self._attributes else 0

    def generate_value(self, variable):
        if variable.cl == self._cmds.index(onId) or variable.cl == self._cmds.index(groupOnId):
            return 100
        elif variable.cl == self._cmds.index(offId) or variable.cl == self._cmds.index(groupOffId):
            return 0
        elif variable.cl == self._cmds.index(setLevelId) or variable.cl == self._cmds.index(groupSetLevelId):
            return min(max(variable.value, 0), 100)
        else:
            super(Light, self).generate_value(variable)

    def on_state(self, topic, jocket):
        result = []

        if topic.entity_addr.funit_type == BRIGHTNESS_LEVEL:
            value = jocket.value if isinstance(jocket.value, int) else 0

            """ isOn """
            v = value > 0
            class_id = self._cmds.index(isOnId)
            if jocket.invalid and class_id in self.values:
                self.values.pop(class_id)
            if self.get_value(class_id) != v:
                to_topic = TopicStateTros3(topic.p_id, self.get_address(class_id))
                var = VariableTRS3(id=self.id, cl=class_id, val=v, invalid=jocket.invalid)
                result.append((to_topic, var))
                if not jocket.invalid:
                    self.set_value(class_id, v)

            """ levelId """
            if levelId in self._cmds:
                class_id = self._cmds.index(levelId)
                v = value
                if jocket.invalid and class_id in self.values:
                    self.values.pop(class_id)
                if self.get_value(class_id) != v:
                    to_topic = TopicStateTros3(topic.p_id, self.get_address(class_id))
                    var = VariableTRS3(id=self.id, cl=class_id, val=v, invalid=jocket.invalid)
                    result.append((to_topic, var))
                    if not jocket.invalid:
                        if value == 0:
                            self.set_last_level()

                        for _subginery in self._subgineries:
                            result += _subginery.on_level_changed(eng=self, level=v)

            """ powerLevelId """
            class_id = self._cmds.index(powerLevelId)
            v = 0 if jocket.invalid else int(self.power * v / 100)
            if jocket.invalid and class_id in self.values:
                self.values.pop(class_id)
            if self.get_value(class_id) != v:
                to_topic = TopicStateTros3(topic.p_id, self.get_address(class_id))
                var = VariableTRS3(id=self.id, cl=class_id, val=v, invalid=jocket.invalid)
                result.append((to_topic, var))
                self.set_value(class_id, v)
                for _subginery in self._subgineries:
                    _subginery.start_update_timer()
        else:
            return super(Light, self).on_state(topic, jocket)

        return result

    def set_last_level(self):
        if levelId in self._cmds:
            self.set_value(self._cmds.index(lastLevelId), self.get_value(self._cmds.index(levelId), 50))


class SwitchingLight(Light):
    _provider_type = lights.RapidaDaliRelay.__name__
    _cmds = [onId, offId, isOnId, groupOnId, groupOffId, powerLevelId, historyRequestId, historyResponseId]

    def set_value(self, key, value): pass


class DimmingLight(Light):
    _provider_type = lights.RapidaDaliDimmer.__name__
    _cmds = [onId, offId, isOnId, setLevelId, levelId, groupOnId, groupOffId, groupSetLevelId, powerLevelId, historyRequestId, historyResponseId, lastLevelId]


class TunableWhiteLight(Light):
    _provider_type = lights.RapidaDaliTunableWhite.__name__
    _cmds = [onId, offId, isOnId, setLevelId, levelId, setColorId, colorId, groupOnId, groupOffId, groupSetLevelId,
             powerLevelId, historyRequestId, historyResponseId, lastLevelId]

    def on_state(self, topic, jocket):
        if topic.entity_addr.funit_type == F_TEMPERATURE:
            value = jocket.value if isinstance(jocket.value, int) else 0
            class_id = self._cmds.index(colorId)
            if jocket.invalid and class_id in self.values:
                self.values.pop(class_id)
            if self.get_value(class_id) != value:
                to_topic = TopicStateTros3(topic.p_id, self.get_address(class_id))
                var = VariableTRS3(id=self.id, cl=class_id, val=value, invalid=jocket.invalid)
                return [(to_topic, var)]
        else:
            return super(TunableWhiteLight, self).on_state(topic, jocket)

    def on_command(self, provider_id, topic, variable):
        if variable.cl == self._cmds.index(setColorId):
            e_addr = self.get_provider_addr(F_TEMPERATURE)
            topic = TopicCommand(topic.p_id, session_id='LE_SID', entity_addr=e_addr)
            return topic, VariableJocket.create_data(id=provider_id, cl=e_addr.funit['id'], action='set', val=variable.value)
        else:
            return super(TunableWhiteLight, self).on_command(provider_id, topic, variable)


class FakeDimmingLight(DimmingLight):
    pass


class RgbLight(Light):
    pass


class DynamicLight(Light):
    pass


"""Sensors"""


class Sensor(Enginery):
    _cmds = [onId, offId, isOnId]

    def on_state(self, topic, jocket):
        res = []
        if topic.entity_addr.funit_type == F_ON:
            class_id = self._cmds.index(isOnId)
            if jocket.invalid and class_id in self.values:
                self.values.pop(class_id)
            if not jocket.invalid:
                self.set_value(class_id, jocket.value)

            to_topic = TopicStateTros3(topic.p_id, self.get_address(class_id))
            var = VariableTRS3(id=self.id, cl=class_id, val=jocket.value, invalid=jocket.invalid)
            res.append((to_topic, var))

            for _subginery in self._subgineries:
                res += (_subginery.on_sensor_on_off(project_id=topic.p_id, eng=self, is_on=jocket.value))

            return res
        else:
            super(Sensor, self).on_state(topic, jocket)

    def generate_value(self, variable):
        return variable.cl == self._cmds.index(onId)


class LightSensor(Sensor):
    _provider_type = 'RapidaDaliLightSensor'
    _funit_type = F_ON


class PresenceSensor(Sensor):
    _provider_type = 'RapidaDaliPresenceSensor'
    _funit_type = F_ON


class LightingArea(Enginery):
    _tuning_type_combo = 'Combo'
    _tuning_type_presence = 'Presence'
    _tuning_type_luminosity = 'Luminosity'

    _def_values = {
        F_ON: False,
        F_DISCOVERY: False,
        F_TUNING_TYPE: _tuning_type_combo,
        F_OCCUPANCY_LEVEL: 1,
        F_VACANCY_LEVEL: 1,
        F_TARGET_LUMINOSITY: 100,
        F_HYSTERESIS: 10,
        F_TUNING_SPEED: 500,
        F_OCCUPANCY_ACTION: ACTION_LAST_LEVEL,
        F_OCCUPANCY_SCENE: 2,
        F_VACANCY_ACTION: ACTION_OFF,
        F_VACANCY_SCENE: 1,
        F_LA_PRESENCE: None,
        F_LA_LUMINOSITY: None,
    }

    def __init__(self, p_id, data, manager_data):
        super(LightingArea, self).__init__(p_id, data, manager_data)
        self.actuations = dict()
        self.presences = dict()
        self.luminosities = dict()
        self.presence_values = dict()
        self.luminosity_values = dict()
        self.dif_rate = 0

    def set_ingridient(self, ingidient_type, ingridient_id, ingridient_eng=None):
        if ingidient_type == ACTUATION_TYPE:
            if ingridient_id not in self.actuations:
                self.actuations[ingridient_id] = []
            if ingridient_eng:
                self.actuations[ingridient_id].append(ingridient_eng)
        elif ingidient_type == PRESENCE_TYPE:
            self.presence_values[ingridient_id] = -1
            if ingridient_id not in self.presences:
                self.presences[ingridient_id] = []
            if ingridient_eng:
                self.presences[ingridient_id].append(ingridient_eng)
        elif ingidient_type == LUMINOSITY_TYPE:
            self.luminosity_values[ingridient_id] = -1
            if ingridient_id not in self.luminosities:
                self.luminosities[ingridient_id] = []
            if ingridient_eng:
                self.luminosities[ingridient_id].append(ingridient_eng)

    def on_state(self, topic, jocket):
        funit_type = topic.entity_addr.funit_type
        funit = self.get_funit(funit_type)
        la_addr = self.get_address(funit['id'])
        to_topic = TopicState(topic.p_id, self.get_address(funit_type))
        new_jocket = VariableJocket.create_data(id=self.id, cl=la_addr.funit_id, action=mqtt.variables.STATE,
                                                val=jocket.value)
        return [(to_topic, new_jocket)]

    def set_value(self, funit_type, value):
        super(LightingArea, self).set_value(funit_type, value)
        settings.set_dump(self, funit_type, value)

    def get_funit(self, funit_type):
        return mqtt.classifier['Lighting'][self.__class__.__name__][funit_type]

    def get_info(self):
        res = []
        for funit_type, def_value in self._def_values.items():
            to_topic = TopicState(self.p_id, self.get_address(funit_type))
            funit = self.get_funit(funit_type)
            value = self.get_value(funit_type)
            _invalid = False
            if value is None:
                if mqtt.VARIANTS in funit:
                    value = funit[mqtt.VARIANTS][0]
                elif def_value is not None:
                    value = def_value
                else:
                    value = funit[mqtt.variables.STATE]()
                    _invalid = True
            self.set_value(funit_type, value)
            jocket = VariableJocket.create_data(id=self.id, cl=funit['id'], action=mqtt.variables.STATE,
                                                val=value, invalid=_invalid)

            res.append((to_topic, jocket))

        return res

    def on_command(self, _, topic, jocket):
        res = []
        act = jocket.action
        funit_type = topic.entity_addr.funit_id
        try:
            funit = self.get_funit(funit_type)
        except KeyError as ex:
            raise JocketError('<<{}>> is not implemented in <<{}>>!'.format(funit_type, self.__class__.__name__))
        else:
            if act in funit:
                if 'func' in funit[act]:
                    if funit[jocket.action]['func'] in dir(self):
                        sig = CommandSignature(topic.session_id, jocket.key)
                        return getattr(self, funit[jocket.action]['func'])(sig, jocket.value)
                    else:
                        raise JocketError(
                            '<<{}>>  of <<{}>> is not implemented in <<{}>>!'.format(funit[jocket.action]['func'],
                                                                                     funit_type,
                                                                                     self.__class__.__name__))
                elif 'value' in funit[act]:
                    reply_topic = mqtt.TopicReply(topic.p_id, topic.session_id)
                    if act == mqtt.variables.SET:
                        try:
                            value = funit[mqtt.variables.STATE](jocket.value)
                        except BaseException as ex:
                             raise CommandError('impossible value({})'.format(jocket.value))

                        if mqtt.VARIANTS in funit:
                            if jocket.value not in funit[mqtt.VARIANTS]:
                                raise CommandError(
                                    'value({}) must include in {}'.format(jocket.value, funit[mqtt.VARIANTS]))

                        if self.get_value(funit_type) != value:
                            self.set_value(funit_type, value)
                            if funit_type == F_ON and value is True:
                                for _id, _part_presence in self.presence_values.items():
                                    if self.presences[_id][0].get_value(Sensor._cmds.index(isOnId)) is True:
                                        if _part_presence is True:
                                            res += self.check_presence(True, False)
                                            break
                            elif funit_type in [F_ON, F_TARGET_LUMINOSITY]:
                                if not value:
                                    res += self.check_luminosity(True)
                                else:
                                    for _lum_id, _lum in self.luminosities.items():
                                        if _lum[0].get_value(Sensor._cmds.index(isOnId), False) is True:
                                            res += self.check_luminosity()
                                            break
                            elif funit_type == F_TUNING_TYPE:
                                if value == self._tuning_type_presence:
                                    for _lum_id, _lum in self.actuations.items():
                                        p_funit = mqtt.classifier[_lum[0].manager.m_type][_lum[0].recipe.provider_type][F_TUNING]
                                        _jocket = VariableJocket.create_data(_lum[0].p_id, p_funit['id'], 'set', val=0)
                                        e_addr = _lum[0].get_provider_addr(F_TUNING)
                                        to_topic = TopicCommand(self.p_id, 'LuminositySetter', e_addr)
                                        res.append((to_topic, _jocket))
                            state_topic = TopicState(topic.p_id, self.get_address(funit_type))
                        else:
                            state_topic = None

                        if state_topic:
                            res.append((state_topic, jocket))

                        return res
                    elif act == mqtt.variables.GET:
                        pass
                    jocket = VariableJocket.create_data(id=self.id, cl=funit['id'],
                                                        action=mqtt.variables.STATE,
                                                        key=jocket.key,
                                                        val=self.get_value(funit_type))

                    return [(reply_topic, jocket)]
                else:
                    raise JocketError(
                        '<<{}>> is not implemented in classifier for <<{}>>!'.format(act, self.__class__.__name__))
            else:
                raise JocketError(
                    '<<{}>>  of <<{}>> is not present in <<{}>>!'.format(act, funit_type, self.__class__.__name__))

    def SetDiscovery(self, sig, value):
        res = []
        _m_id = None
        funit_type = F_DISCOVERY
        for _stack in [self.actuations, self.presences, self.luminosities]:
            for _p_id, _p in _stack.items():
                for _eng in _p:
                    funit = mqtt.classifier[_eng.manager.m_type][_eng.recipe.provider_type][funit_type]
                    jocket = VariableJocket.create_data(_p_id, funit['id'], 'set', val=value, key=sig.key)
                    e_addr = self.get_provider_addr(funit_type)
                    to_topic = TopicCommand(self.p_id, funit_type+'Setter', e_addr)
                    res.append((to_topic, jocket))

        self.set_value(F_DISCOVERY, value)
        res.append(self.publish_state(funit_type, value))

        return res

    def on_luminosity_event(self, jocket):
        res = []
        val = jocket.value
        _has_break = True

        if self.luminosity_values[jocket.id] != val:
            self.luminosity_values[jocket.id] = val
            avg_lum = self.get_avg_lum()
            self.values[F_LA_LUMINOSITY] = avg_lum
            res.append((self.publish_state(F_LA_LUMINOSITY, avg_lum)))

        if self.get_value(F_ON, False) is False:
            return res

        _tuning_type = self.get_value(F_TUNING_TYPE)
        if _tuning_type != self._tuning_type_combo and _tuning_type != self._tuning_type_luminosity:
            return res
        elif _tuning_type == self._tuning_type_combo or _tuning_type == self._tuning_type_presence:
            for _presence_id in self.presence_values:
                if self.presence_values[_presence_id] is True and self.presences[_presence_id][0].get_value(Sensor._cmds.index(isOnId)) is True:
                    _has_break = False
                    break
        else:
            _has_break = False

        if _has_break is True:
            return res

        return res + self.check_luminosity()

    def on_presence_event(self, jocket):
        res = []
        val = jocket.value

        if self.presence_values[jocket.id] == val:
            return res
        self.presence_values[jocket.id] = val

        if val is False:
            _total_presence = False
            for _id, _part_presence in self.presence_values.items():
                if self.presences[_id][0].get_value(Sensor._cmds.index(isOnId)) is True:
                    _total_presence = _part_presence is True or _total_presence
                    if _part_presence is True:
                        break
            val = _total_presence

        if self.get_value(F_LA_PRESENCE) == val:
            return res

        res.append((self.publish_state(F_LA_PRESENCE, val)))

        if self.get_value(F_ON, False) is False:
            return res

        res += self.check_presence(val)

        return res

    def check_presence(self, val, check_lum=True):
        res = []
        _tuning_type = self.get_value(F_TUNING_TYPE)
        if _tuning_type != self._tuning_type_combo and _tuning_type != self._tuning_type_presence:
            return res

        for p_id in self.actuations:
            if p_id in self.actuations:
                for eng in self.actuations[p_id]:
                    class_id = None
                    value = None
                    if val is True:
                        _action = self.get_value(F_OCCUPANCY_ACTION)
                        if _action == ACTION_MAX_LEVEL:
                            res.append(eng.on_command_j(self.p_id, F_RECALL_MAX_LEVEL, True))
                        elif _action == ACTION_LEVEL:
                            class_id = eng._cmds.index(setLevelId)
                            value = self.get_value(F_OCCUPANCY_LEVEL, 0)
                        elif _action == ACTION_SCENE:
                            res.append(eng.on_command_j(self.p_id, F_SCENE, self.get_value(F_OCCUPANCY_SCENE)))
                        else:  # _action == ACTION_LAST_LEVEL
                            class_id = eng._cmds.index(setLevelId)
                            if lastLevelId in eng._cmds:
                                value = eng.get_value(eng._cmds.index(lastLevelId), 50)
                    else:
                        _action = self.get_value(F_VACANCY_ACTION)
                        if _action == ACTION_MIN_LEVEL:
                            res.append(eng.on_command_j(self.p_id, F_RECALL_MIN_LEVEL, True))
                        elif _action == ACTION_LEVEL:
                            class_id = eng._cmds.index(setLevelId)
                            value = self.get_value(F_VACANCY_LEVEL, 0)
                        elif _action == ACTION_SCENE:
                            res.append(eng.on_command_j(self.p_id, F_SCENE, self.get_value(F_VACANCY_SCENE)))
                        else:
                            class_id = eng._cmds.index(offId)
                            value = True

                    if class_id is not None and value is not None:
                        to_topic = mqtt.TopicCommandTros3(self.p_id, EngineryAddress(eng.id, class_id))
                        res.append(eng.on_command(eng.recipe.id, to_topic,
                                                  VariableTRS3(id=eng.id, cl=class_id, val=value)))

        if check_lum:
            res += self.check_luminosity(force_off=not val)

        return res

    def check_luminosity(self, force_off=False):
        res = []

        _tuning_type = self.get_value(F_TUNING_TYPE)
        if _tuning_type != self._tuning_type_combo and _tuning_type != self._tuning_type_luminosity:
            return res

        avg_lum = self.get_value(F_LA_LUMINOSITY, 0)
        _target = self.get_value(F_TARGET_LUMINOSITY)
        _hysteresis = self.get_value(F_HYSTERESIS) / 100
        _dif_rate = 0
        if _target != 0:
            _dif_rate = (_target - avg_lum) / _target
        if force_off:
            _dif_rate = 0
        elif abs(_dif_rate) <= _hysteresis:
            _dif_rate = 0

        # if self.dif_rate * _dif_rate > 0:
        #     return res
        if self.dif_rate == _dif_rate:
            return res

        self.dif_rate = int(_dif_rate*100)/100

        for _p_id in self.actuations:
            for _p in self.actuations[_p_id]:
                funit = mqtt.classifier[_p.manager.m_type][_p.recipe.provider_type][F_TUNING]
                jocket = VariableJocket.create_data(_p_id, funit['id'], 'set', val=self.dif_rate)
                jocket.data['data']['speed'] = self.get_value(F_TUNING_SPEED) / 1000
                e_addr = _p.get_provider_addr(F_TUNING)
                to_topic = TopicCommand(self.p_id, 'LuminositySetter', e_addr)
                res.append((to_topic, jocket))

        return res

    def get_avg_lum(self):
        avg_lum = 0
        avg_cnt = 0

        for d_id, d_val in self.luminosity_values.items():
            if self.luminosities[d_id][0].get_value(Sensor._cmds.index(isOnId), False) is True:
                val = d_val
                if val is None:
                    continue
                if val != -1:
                    avg_lum += val
                    avg_cnt += 1

        if avg_cnt > 1:
            avg_lum = round(avg_lum / avg_cnt)

        return avg_lum
