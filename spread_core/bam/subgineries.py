import threading

from spread_core.bam import engineries
from spread_core.bam.entities import Entity
from spread_core.mqtt import TopicCommandTros3, TopicStateTros3, SubgineryAddress
from spread_core.mqtt.variables import VariableTRS3
from spread_core.tools import settings

onId = 'onId'
offId = 'offId'
isOnId = 'isOnId'
isOffId = 'isOffId'
saveScene1Id = 'saveScene1Id'
loadScene1Id = 'loadScene1Id'
isMatchScene1Id = 'isMatchScene1Id'
saveScene2Id = 'saveScene2Id'
loadScene2Id = 'loadScene2Id'
isMatchScene2Id = 'isMatchScene2Id'
powerLevelId = 'powerLevelId'
historyRequestId = 'historyRequestId'
historyResponseId = 'historyResponseId'
lightSensorsOnId = 'lightSensorsOnId'
lightSensorsOffId = 'lightSensorsOffId'
isLightSensorsOnId = 'isLightSensorsOnId'
isLightSensorsOffId = 'isLightSensorsOffId'
presenceSensorsOnId = 'presenceSensorsOnId'
presenceSensorsOffId = 'presenceSensorsOffId'
isPresenceSensorsOnId = 'isPresenceSensorsOnId'
isPresenceSensorsOffId = 'isPresenceSensorsOffId'
setTemperatureId = 'setTemperatureId'


SCENE_1 = 'scene_1'
SCENE_2 = 'scene_2'


class Subginery(Entity):
    def __init__(self, project_id, data):
        super().__init__(data['id'])
        self.project_id = project_id
        self._location_id = data['locationID']
        self._key = data['key']
        self._engineries = dict.fromkeys(data['engineries'])
        self.update_timer = None

    location_id = property(fget=lambda self: self._location_id, doc='location_id')


class Lighting(Subginery):
    _cmds = [onId, offId, isOnId, isOffId,
             saveScene1Id, loadScene1Id, isMatchScene1Id,
             saveScene2Id, loadScene2Id, isMatchScene2Id,
             powerLevelId, historyRequestId, historyResponseId,
             lightSensorsOnId, lightSensorsOffId, isLightSensorsOnId, isLightSensorsOffId,
             presenceSensorsOnId, presenceSensorsOffId, isPresenceSensorsOnId, isPresenceSensorsOffId, setTemperatureId]

    def __init__(self, project_id, data):
        super().__init__(project_id, data)

        self.power_level = 0
        self._scenes = self._get_scenes()
        self.bad_is_on = []
        self.bad_is_off = []
        self.bad_scene1 = []
        self.bad_scene2 = []
        self.bad_presence_on = []
        self.bad_presence_off = []
        self.bad_lum_on = []
        self.bad_lum_off = []
        self.update_handler = None

    def get_address(self, class_id):
        return SubgineryAddress(self.id, class_id)

    def set_update_handler(self, update_handler):
        self.update_handler = update_handler

    def publish_state(self, project_id, class_id, value, invalid=False):
        self.set_value(class_id, value)
        _addr = self.get_address(class_id)
        topic = TopicStateTros3(project_id, _addr)
        data = VariableTRS3(id=self.id, cl=class_id, val=value, invalid=invalid)
        return topic, data

    def on_sensor_on_off(self, project_id, eng, is_on):
        res = []

        if isinstance(eng, engineries.PresenceSensor):
            on_class_id = self._cmds.index(isPresenceSensorsOnId)
            on_stack = self.bad_presence_on
            off_class_id = self._cmds.index(isPresenceSensorsOffId)
            off_stack = self.bad_presence_off
        elif isinstance(eng, engineries.LightSensor):
            on_class_id = self._cmds.index(isLightSensorsOnId)
            on_stack = self.bad_lum_on
            off_class_id = self._cmds.index(isLightSensorsOffId)
            off_stack = self.bad_lum_off
        else:
            return res

        if is_on:
            if eng.id not in off_stack:
                off_stack.append(eng.id)
            if self.get_value(off_class_id) is not False:
                res.append(self.publish_state(project_id, off_class_id, False))

            if eng.id in on_stack:
                on_stack.remove(eng.id)
                if len(on_stack) == 0 and self.get_value(on_class_id) is not True:
                    res.append(self.publish_state(project_id, on_class_id, True))
            elif self.get_value(on_class_id) is None:
                res.append(self.publish_state(project_id, on_class_id, True))

        else:
            if eng.id not in on_stack:
                on_stack.append(eng.id)
                if self.get_value(on_class_id) is not False:
                    res.append(self.publish_state(project_id, on_class_id, False))

            if eng.id in off_stack:
                off_stack.remove(eng.id)
                if len(off_stack) == 0 and self.get_value(off_class_id) is not True:
                    res.append(self.publish_state(project_id, off_class_id, True))
            elif self.get_value(off_class_id) is None:
                res.append(self.publish_state(project_id, off_class_id, True))

        return res

    def on_level_changed(self, eng, level):
        res = []

        is_on_class = self._cmds.index(isOnId)
        is_off_class = self._cmds.index(isOffId)
        on_stack = self.bad_is_on
        off_stack = self.bad_is_off

        scene_1_class = self._cmds.index(isMatchScene1Id)
        scene_1_stack = self.bad_scene1
        scene_2_class = self._cmds.index(isMatchScene2Id)
        scene_2_stack = self.bad_scene2

        if level == 0:
            if eng.id not in on_stack:
                on_stack.append(eng.id)
                if self.get_value(is_on_class) is not False:
                    res.append(self.publish_state(self.project_id, is_on_class, False))

            if eng.id in off_stack:
                off_stack.remove(eng.id)
                if len(off_stack) == 0 and self.get_value(is_off_class) is not True:
                    res.append(self.publish_state(self.project_id, is_off_class, True))
        else:
            if eng.id not in off_stack:
                off_stack.append(eng.id)
                if self.get_value(is_off_class) is not False:
                    res.append(self.publish_state(self.project_id, is_off_class, False))

            if eng.id in on_stack:
                on_stack.remove(eng.id)
                if len(on_stack) == 0 and self.get_value(is_on_class) is not True:
                    res.append(self.publish_state(self.project_id, is_on_class, True))

        for scene_name, scene_stack, scene_class in [[SCENE_1, scene_1_stack, scene_1_class], [SCENE_2, scene_2_stack, scene_2_class]]:
            if scene_name in self._scenes and eng.id in self._scenes[scene_name]:
                if self._scenes[scene_name][eng.id] == level:
                    if eng.id in scene_stack:
                        scene_stack.remove(eng.id)
                        if len(scene_stack) == 0 and self.get_value(scene_class) is not True:
                            res.append(self.publish_state(self.project_id, scene_class, True))
                    elif self.get_value(scene_class) is None:
                        res.append(self.publish_state(self.project_id, scene_class, True))
                elif eng.id not in scene_stack:
                    scene_stack.append(eng.id)
                    if self.get_value(scene_class) is not False:
                        res.append(self.publish_state(self.project_id, scene_class, False))

        return res

    def _get_scenes(self):
        res = dict()
        dump = settings.get_dump_entity(self)
        if SCENE_1 in dump:
            res[SCENE_1] = dump[SCENE_1]
        if SCENE_2 in dump:
            res[SCENE_2] = dump[SCENE_2]

        return res

    def update_power(self):
        self.power_level = 0
        for e_id, _enginery in self._engineries.items():
            if isinstance(_enginery, engineries.Light):
                self.power_level += _enginery.get_value(_enginery._cmds.index(engineries.powerLevelId), 0)
        class_id = self._cmds.index(powerLevelId)
        to_topic = TopicStateTros3(self.project_id, self.get_address(class_id))
        var = VariableTRS3(id=self.id, cl=class_id, val=self.power_level)
        self.update_handler(to_topic, var)

    def start_update_timer(self):
        if self.update_timer:
            self.update_timer.cancel()
        self.update_timer = threading.Timer(3, function=self.update_power)
        self.update_timer.setName('sb_update_timer')
        self.update_timer.start()

    def on_command(self, topic, variable):
        res = []
        cmd = self._cmds[variable.cl]
        e_class = None
        on_class = None
        if cmd == onId or cmd == offId:
            e_class = engineries.Light
            on_class = onId
        elif cmd == lightSensorsOnId or cmd == lightSensorsOffId:
            e_class = engineries.LightSensor
            on_class = lightSensorsOnId
        elif cmd == presenceSensorsOnId or cmd == presenceSensorsOffId:
            e_class = engineries.PresenceSensor
            on_class = presenceSensorsOnId
        elif cmd == saveScene1Id or cmd == saveScene2Id:
            _scene_id = SCENE_1 if cmd == saveScene1Id else SCENE_2
            _new_scene = dict()
            for _e_id, _enginery in self._engineries.items():
                if isinstance(_enginery, engineries.Light):
                    _value = _enginery.get_value(_enginery._cmds.index(engineries.levelId))
                    if _value is not None:
                        _new_scene[_enginery.id] = _enginery.get_value(_enginery._cmds.index(engineries.levelId))
            self._scenes[_scene_id] = _new_scene
            settings.set_dump(self, _scene_id, _new_scene)
            return res
        elif cmd == loadScene1Id or cmd == loadScene2Id:
            _scene_id = SCENE_1 if cmd == loadScene1Id else SCENE_2

            if _scene_id in self._scenes:
                for _e_id, _value in self._scenes[_scene_id].items():
                    if _e_id in self._engineries:
                        _enginery = self._engineries[_e_id]
                        # _c_value = _enginery.get_value(_enginery._cmds.index(engineries.levelId))
                        # if _c_value != _value:
                        _class_id = _enginery._cmds.index(engineries.setLevelId)
                        _e_addr = _enginery.get_address(_class_id)
                        _topic = TopicCommandTros3(_enginery.p_id, _e_addr)
                        _p_id = _enginery.recipe.id
                        _variable = VariableTRS3(id=_enginery.id, cl=_class_id, val=_value)
                        res.append(_enginery.on_command(_p_id, _topic, _variable))
        elif cmd == setTemperatureId:
            for _e_id, _enginery in self._engineries.items():
                if isinstance(_enginery, engineries.TunableWhiteLight):
                    _class_id = _enginery._cmds.index(engineries.setColorId)
                    _e_addr = _enginery.get_address(_class_id)
                    _topic = TopicCommandTros3(_enginery.p_id, _e_addr)
                    _p_id = _enginery.recipe.id
                    _variable = VariableTRS3(id=_enginery.id, cl=_class_id, val=variable.value)
                    res.append(_enginery.on_command(_p_id, _topic, _variable))
        else:
            print('unknown cmd({})'.format(cmd))

        if e_class is not None and on_class is not None:
            for e_id, _enginery in self._engineries.items():
                if isinstance(_enginery, e_class):
                    class_id = _enginery._cmds.index(onId if cmd == on_class else offId)
                    _enginery.get_address(onId)
                    _e_addr = _enginery.get_address(class_id)
                    _topic = TopicCommandTros3(_enginery.p_id, _e_addr)
                    _p_id = _enginery.recipe.id
                    _variable = VariableTRS3(id=_enginery.id, cl=class_id, val=True)
                    res.append(_enginery.on_command(_p_id, _topic, _variable))
        return res
