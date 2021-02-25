import json
from datetime import datetime

import spread_core.bam.const as bam_const
import spread_core.mqtt as mqtt
from spread_core.bam import engineries, subgineries, generator
from spread_core.bam.dali import *
from spread_core.errors import project_errors
from spread_core.errors.project_errors import ClassifierError
from spread_core.mqtt import spread as spread
from spread_core.mqtt.variables import VariableJocket, VariableTRS3, VariableReader
from spread_core.tools import settings
from spread_core.tools.service_launcher import Launcher, logging

PROJECT_ID = settings.config[settings.PROJECT_ID]


class Frontier(Launcher):
    _dumped = False

    def __init__(self):
        self._manager = self
        self.subgineries = {}
        self.engineries = {}
        self.server_id = 'Здесь_могла_быть_ваша_реклама!!'
        super(Frontier, self).__init__()

    def start(self):
        try:
            self.subscribe(mqtt.TopicProject(PROJECT_ID, bam_const.SERVERS + '.json'))
        except BaseException as ex:
            logging.exception(ex)

    def on_message(self, mosq, obj, msg):
        try:
            if spread.topic.SpreadTopic.protocol in msg.topic:
                topic = spread.topic.topic_of(msg.topic)

                if isinstance(topic, (spread.topic.Set, spread.topic.Renew)):
                    self.on_spread(topic, msg.payload)
                else:
                    logging.debug(f'[NO MOVE] {topic}')
            else:
                topic = mqtt.mqtt.of(msg.topic)

                if isinstance(topic, mqtt.TopicProject):
                    self.on_project(topic, json.loads(msg.payload.decode()))
                elif isinstance(topic, (mqtt.TopicStateTros3, mqtt.TopicCommandTros3)):
                    self.on_tros3(topic, msg.payload)
                elif isinstance(topic, (mqtt.TopicCommand, mqtt.TopicState)):
                    self.on_jocket(topic, msg.payload)
                else:
                    logging.debug(f'[NO MOVE] {topic}')
        except project_errors.TopicError as ex:
            logging.warning(ex)
        except BaseException as ex:
            logging.exception(ex)

    def on_project(self, topic, data):
        self.unsubscribe(topic)

        if bam_const.SERVERS in data:
            self.server_id = data[bam_const.SERVERS][0]['id']
            self.subscribe(mqtt.TopicProject(PROJECT_ID, bam_const.ENGINERIES + '.json'))

        elif bam_const.ENGINERIES in data:
            cnt = 0
            for e_data in data[bam_const.ENGINERIES]:
                try:
                    self.engineries[e_data['id']] = generator.generate_enginery(PROJECT_ID, e_data, {})
                except project_errors.ProjectError as ex:
                    continue

            self.subscribe(mqtt.TopicProject(PROJECT_ID, bam_const.SUBGINERIES + '.json'))

        if bam_const.SUBGINERIES in data:
            for e_data in data[bam_const.SUBGINERIES]:
                try:
                    self.subgineries[e_data['id']] = generator.generate_subginery(PROJECT_ID, e_data)
                except project_errors.ProjectError as ex:
                    continue

            self.subscribe(mqtt.TopicCommandTros3(PROJECT_ID))
            self.subscribe(mqtt.TopicStateTros3(PROJECT_ID, '#'))
            self.subscribe(mqtt.TopicCommand(PROJECT_ID))
            self.subscribe(mqtt.TopicState(PROJECT_ID, '#'))
            self.subscribe(spread.topic.Set(spread.address.BroadcastAddress(PROJECT_ID)))
            self.subscribe(spread.topic.Renew(spread.address.BroadcastAddress(PROJECT_ID)))

    def on_exit(self, sig, frame):
        super(Frontier, self).on_exit(sig, frame)

    def on_jocket(self, _topic, data):
        _var = VariableJocket(json.loads(data.decode()))
        _address = _topic.entity_addr
        if isinstance(_address, mqtt.EngineryAddress):
            e_id = int(_address.entity_id)
            if e_id in self.engineries:
                e_data = self.engineries[e_id]
                address = spread.address.EngineryAddress(_topic.p_id, e_data.__class__.__name__, e_id, _address.funit_id)
            elif e_id in self.subgineries:
                e_data = self.subgineries[e_id]
                address = spread.address.SubgineryAddress(_topic.p_id, e_data.location_id, e_data.__class__.__name__, _address.funit_id)
            else:
                logging.debug(f'Unknown enginery/subgnery ({_address})')
                return
        elif isinstance(_address, mqtt.ProviderAddress):
            address = spread.address.ProviderAddress(PROJECT_ID, _address.manager_type, _address.manager_id,
                                                     _address.provider_type, _address.provider_id, _address.funit_type)
        elif isinstance(_address, mqtt.ManagerAddress):
            address = spread.address.ManagerAddress(PROJECT_ID, _address.manager_type, _address.manager_id, _address.funit_type)
        else:
            logging.debug(f'Unsupported address ({_address.__class__.__name__})')
            return

        if isinstance(_topic, mqtt.TopicState):
            topic = spread.topic.State(address)
        elif isinstance(_topic, mqtt.TopicCommand):
            topic = spread.topic.Event(address)
        else:
            logging.debug(f'Unsupported topic ({_topic.__class__.__name__})')
            return

        var = spread.variable.Variable(_var.value, timestamp=datetime.fromisoformat(str(_var.timeStamp)))
        self.publish(topic, var, retain=isinstance(_topic, mqtt.TopicState))

    def on_spread(self, _topic: (spread.topic.Set, spread.topic.Renew), data):
        data = json.loads(data.decode())
        _var = spread.variable.Variable(**data)
        _address = _topic.entity_address
        if isinstance(_topic, spread.topic.Set):
            if isinstance(_topic.entity_address, (spread.address.EngineryAddress, spread.address.SubgineryAddress)):
                value = True
                if _address.funit_type == F_ON:
                    if _var.value:
                        funit_id = engineries.onId
                    else:
                        funit_id = engineries.offId
                elif _address.funit_type == F_BrightnessLevel:
                    funit_id = engineries.setLevelId
                    value = _var.value
                elif _address.funit_type == F_GROUP_LEVEL:
                    if _var.value == 0:
                        funit_id = engineries.groupOffId
                    elif _var.value == 100:
                        funit_id = engineries.groupOnId
                    else:
                        funit_id = engineries.groupSetLevelId
                elif _address.funit_type == F_PresenceSensorsOn:
                    if _var.value:
                        funit_id = subgineries.presenceSensorsOnId
                    else:
                        funit_id = subgineries.presenceSensorsOffId
                elif _address.funit_type == F_LightSensorsOn:
                    if _var.value:
                        funit_id = subgineries.lightSensorsOnId
                    else:
                        funit_id = subgineries.lightSensorsOffId
                else:
                    logging.debug(f'Unsupported funit "{_address.funit_type}"')
                    return

                if isinstance(_address, spread.address.EngineryAddress):
                    _entity = self.engineries[_address.id]
                elif isinstance(_address, spread.address.SubgineryAddress):
                    _entity = self.subgineries[_address.id]
                else:
                    logging.debug(f'Unsupported entity "{_address.__class__.__name__}"')
                    return

                cl = _entity._cmds.index(funit_id)
                var = VariableTRS3(None, _address.id, cl, value, _var.invalid)
                topic = mqtt.TopicCommandTros3(PROJECT_ID, mqtt.EngineryAddress(_address.id, cl))
            else:
                try:
                    address = spread_address_to_mqtt(self.server_id, _address)
                    funit = get_funit(_address)
                except ClassifierError as ex:
                    logging.debug(ex)
                    return
                except BaseException:
                    logging.debug(f'Unsupported address "{_address.__class__.__name__}"')
                    return
                else:
                    var = VariableJocket.create_data(_address.id, funit['id'], 'set', _var.value, invalid=_var.invalid)
                    topic = mqtt.TopicCommand(PROJECT_ID, 'Frontier_SID', address)
        elif isinstance(_topic, spread.topic.Renew):
            try:
                topic = mqtt.TopicCommand(spread_address_to_mqtt(self.server_id, _address))
                funit = get_funit(_address)
            except ClassifierError as ex:
                logging.debug(ex)
                return
            except BaseException:
                logging.debug(f'Unsupported address "{_address.__class__.__name__} of {_topic.__class__.__name__}"')
                return
            else:
                var = VariableJocket.create_data(_address.id, funit['id'], 'get', _var.value)
        else:
            logging.debug(f'Unsupported topic "{_topic.__class__.__name__}"')
            return

        self.publish(topic, var, retain=False)

    def on_tros3(self, _topic: mqtt.TopicData, data):
        _var = VariableTRS3(VariableReader(data))
        e_id = _var.id
        timestamp = None

        if _var.timeStamp:
            timestamp = datetime.fromisoformat(str(_var.timeStamp))

        if e_id in self.engineries:
            e_data = self.engineries[e_id]
            funit_name = e_data._cmds[_var.cl]

            if isinstance(_topic, mqtt.TopicStateTros3):
                value = _var.value

                if funit_name == engineries.isOnId:
                    funit_type = F_ON
                elif funit_name == engineries.levelId:
                    funit_type = F_BrightnessLevel
                elif funit_name == engineries.powerLevelId:
                    funit_type = F_PowerLevel
                else:
                    logging.debug(f'Unsupported funit "{funit_name}"')
                    return

                if _var.invalid:
                    value = None

                topic = spread.topic.State(
                    spread.address.EngineryAddress(_topic.p_id, e_data.__class__.__name__, e_id, funit_type)
                )
                retain = True
            elif isinstance(_topic, mqtt.TopicCommandTros3):
                if funit_name == engineries.onId:
                    funit_type = F_ON
                    value = True
                elif funit_name == engineries.offId:
                    funit_type = F_ON
                    value = False
                elif funit_name == engineries.setLevelId:
                    funit_type = F_BrightnessLevel
                    value = _var.value
                elif funit_name == engineries.groupOnId:
                    funit_type = F_GROUP_LEVEL
                    value = 100
                elif funit_name == engineries.groupOffId:
                    funit_type = F_GROUP_LEVEL
                    value = 0
                elif funit_name == engineries.groupSetLevelId:
                    funit_type = F_GROUP_LEVEL
                    value = _var.value
                else:
                    logging.debug(f'Unsupported funit "{funit_name}"')
                    return

                topic = spread.topic.Event(
                    spread.address.EngineryAddress(_topic.p_id, e_data.__class__.__name__, e_id, funit_type)
                )
                retain = False
            else:
                return

        elif e_id in self.subgineries:
            e_data = self.subgineries[e_id]
            funit_name = e_data._cmds[_var.cl]

            if isinstance(_topic, mqtt.TopicStateTros3):
                value = _var.value

                if funit_name == subgineries.isOnId:
                    funit_type = F_SwitchOn
                elif funit_name == subgineries.isOffId:
                    funit_type = F_SwitchOff
                elif funit_name == subgineries.isMatchScene1Id:
                    funit_type = F_Scene1On
                elif funit_name == subgineries.isMatchScene2Id:
                    funit_type = F_Scene2On
                elif funit_name == subgineries.powerLevelId:
                    funit_type = F_PowerLevel
                elif funit_name == subgineries.isLightSensorsOnId:
                    funit_type = F_LightSensorsOn
                    value = True
                elif funit_name == subgineries.isLightSensorsOffId:
                    funit_type = F_LightSensorsOn
                    value = False
                elif funit_name == subgineries.isPresenceSensorsOnId:
                    funit_type = F_PresenceSensorsOn
                    value = True
                elif funit_name == subgineries.isPresenceSensorsOffId:
                    funit_type = F_PresenceSensorsOn
                    value = False
                else:
                    logging.debug(f'Unsupported funit "{funit_name}"')
                    return

                if _var.invalid:
                    value = None

                topic = spread.topic.State(
                    spread.address.SubgineryAddress(_topic.p_id, e_data.location_id, e_data.__class__.__name__, funit_type)
                )
                retain = True
            elif isinstance(_topic, mqtt.TopicCommandTros3):
                if funit_name == subgineries.onId:
                    funit_type = F_ON
                    value = True
                elif funit_name == subgineries.offId:
                    funit_type = F_ON
                    value = False
                # elif funit_name == subgineries.loadScene1Id:
                # elif funit_name == subgineries.loadScene2Id:
                elif funit_name == subgineries.presenceSensorsOnId:
                    funit_type = F_PresenceSensorsOn
                    value = True
                elif funit_name == subgineries.presenceSensorsOffId:
                    funit_type = F_PresenceSensorsOn
                    value = False
                elif funit_name == subgineries.lightSensorsOnId:
                    funit_type = F_LightSensorsOn
                    value = True
                elif funit_name == subgineries.lightSensorsOffId:
                    funit_type = F_LightSensorsOn
                    value = False
                else:
                    logging.debug(f'Unsupported funit "{funit_name}"')
                    return

                topic = spread.topic.Event(
                    spread.address.SubgineryAddress(_topic.p_id, e_data.location_id, e_data.__class__.__name__, funit_type)
                )
                retain = False
            else:
                logging.debug(f'Unsupported topic "{_topic}"')
                return
        else:
            logging.debug(f'Unknown entity({e_id})')
            return

        var = spread.variable.Variable(value, timestamp=timestamp)

        self.publish(topic=topic, data=var, retain=retain)


def get_funit(address: spread.address.ProviderAddress):
    if address.manager_type in mqtt.classifier:
        funit = mqtt.classifier[address.manager_type]
        if address.type in funit:
            funit = funit[address.type]
            if address.funit_type in funit:
                return funit[address.funit_type]

    raise ClassifierError('Объект {} отсутствует в classifier[{}]'.format(address.funit_type, address.manager_type))


def spread_address_to_mqtt(server_id: (str, int), _address: spread.address.EntityAddress):
    if isinstance(_address, spread.address.ProviderAddress):
        address = mqtt.ProviderAddress('AppServer', server_id,
                                       _address.manager_type, _address.manager_id,
                                       _address.type, _address.id,
                                       _address.funit_type)
    elif isinstance(_address, spread.address.ManagerAddress):
        address = mqtt.ProviderAddress('AppServer', server_id, _address.type,
                                       _address.id, _address.funit_type)
    else:
        raise

    return address


if __name__ == '__main__':
    Frontier()
