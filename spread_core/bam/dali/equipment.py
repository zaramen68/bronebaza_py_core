import json
import threading

import spread_core.mqtt.variables
from spread_core.bam import engineries, generator
from spread_core.bam.const import *
from spread_core.bam.dali import *
from spread_core.bam.engineries import LightingArea
from spread_core.bam.entities import Entity
from spread_core.bam.recipe.recipe import Recipe
from spread_core.errors.project_errors import ProjectError, ProviderNotPresent, JocketError, EngineryNotPresent
from spread_core.mqtt import *
from spread_core.tools.manager_interface import ManagerOfBroker
from spread_core.tools.settings import logging, config

LOG_SUBSCRIBES = 'LOG_SUBSCRIBES'

LOG_PROJECT_SUBSCRIBES = LOG_SUBSCRIBES in config and config['LOG_SUBSCRIBES'] is True


class LightingEquipment(Entity, ManagerOfBroker):
    EVENT_TOPICS = [STATE_C_LUMINOSITY, STATE_C_PRESENCE]
    STATE_TOPICS = [F_ON, BRIGHTNESS_LEVEL, TRIGGER, F_TEMPERATURE] + EVENT_TOPICS

    def __init__(self, p_id):
        Entity.__init__(self, p_id)
        self.s_id = 0
        self.update_event = threading.Event()

        self._managers = dict()
        self._subgineries = dict()
        self._lighting_areas = dict()
        self._stopped = False
        self._queue = []

    def set_broker(self, mqttc):
        ManagerOfBroker.__init__(self, mqttc)

    def start(self):
        self.subscribe(TopicProject(self.id, '{}.json'.format(SERVERS)))

    def on_project(self, data):
        data = json.loads(data)
        if SERVERS in data:
            self.unsubscribe(TopicProject(self.id, '{}.json'.format(SERVERS)), LOG_PROJECT_SUBSCRIBES)
            self.s_id = data[SERVERS][0][ID]
            self.subscribe(TopicProject(self.id, '{}.json'.format(MANAGERS)), LOG_PROJECT_SUBSCRIBES)
        elif MANAGERS in data:
            self.unsubscribe(TopicProject(self.id, '{}.json'.format(MANAGERS)), LOG_PROJECT_SUBSCRIBES)
            for item in data[MANAGERS]:
                if item[ID] not in self._managers:
                    self._managers[item[ID]] = dict(data=item)
                    self._managers[item[ID]][ENGINERIES] = dict()
                    self._managers[item[ID]][PROVIDERS] = dict()
            self.subscribe(TopicProject(self.id, '{}.json'.format(PROVIDERS)), LOG_PROJECT_SUBSCRIBES)
        elif PROVIDERS in data:
            self.unsubscribe(TopicProject(self.id, '{}.json'.format(PROVIDERS)), LOG_PROJECT_SUBSCRIBES)
            for item in data[PROVIDERS]:
                if item[MANAGER_ID] in self._managers:
                    if item[ID] not in self._managers[item[MANAGER_ID]][PROVIDERS]:
                        self._managers[item[MANAGER_ID]][PROVIDERS][item[ID]] = Recipe(item[ID], item[TYPE])
            self.subscribe(TopicProject(self.id, '{}.json'.format(SUBGINERIES)), LOG_PROJECT_SUBSCRIBES)
        elif SUBGINERIES in data:
            self.unsubscribe(TopicProject(self.id, '{}.json'.format(SUBGINERIES)), LOG_PROJECT_SUBSCRIBES)
            for s_data in data[SUBGINERIES]:
                try:
                    self._subgineries[s_data[ID]] = generator.generate_subginery(self.id, s_data)
                    self._subgineries[s_data[ID]].set_update_handler(self.add_to_queue)
                except ProjectError as ex:
                    logging.warning(ex)
            self.subscribe(TopicProject(self.id, '{}.json'.format(ENGINERIES)), LOG_PROJECT_SUBSCRIBES)
        elif ENGINERIES in data:
            try:
                self.unsubscribe(TopicProject(self.id, '{}.json'.format(ENGINERIES)), LOG_PROJECT_SUBSCRIBES)
                for e_data in data[ENGINERIES]:
                    e_id = e_data[ID]
                    if RECIPE in e_data and TYPE in e_data[RECIPE] and INGREDIENTS in e_data[RECIPE]:
                        if e_data[RECIPE][TYPE] == 'Simple' and len(e_data[RECIPE][INGREDIENTS]) > 0:
                            p_id = e_data[RECIPE][INGREDIENTS][0][ID]
                            for m_id in self._managers:
                                if p_id in self._managers[m_id][PROVIDERS]:
                                    try:
                                        _eng = generator.generate_enginery(self.id, e_data, self._managers[m_id]['data'])
                                    except ProjectError as ex:
                                        logging.warning(ex)
                                    else:
                                        for _s_id in self._subgineries:
                                            if e_id in self._subgineries[_s_id]._engineries:
                                                _eng.set_subginery(self._subgineries[_s_id])
                                                self._subgineries[_s_id]._engineries[e_id] = _eng
                                        self._managers[m_id][PROVIDERS][p_id].set_enginery(_eng)
                                        _eng.set_provider(self._managers[m_id][PROVIDERS][p_id])
                                        self._managers[m_id][ENGINERIES][e_id] = p_id
                                    finally:
                                        break
                for e_data in data[ENGINERIES]:
                    if RECIPE in e_data and TYPE in e_data[RECIPE] and INGREDIENTS in e_data[RECIPE]:
                        if e_data[RECIPE][TYPE] == 'Piecemeal' and e_data[TYPE] == LightingArea.__name__:
                            la = generator.generate_enginery(self.id, e_data, {})
                            for p_data in e_data[RECIPE][INGREDIENTS]:
                                p_id = p_data[ID]
                                for m_id in self._managers:
                                    if p_id in self._managers[m_id][PROVIDERS]:
                                        if len(self._managers[m_id][PROVIDERS][p_data[ID]].engs) == 0:
                                            eng = engineries.FakeDimmingLight(
                                                p_id,
                                                {
                                                    ID: -1,
                                                    'label': 'fake_label',
                                                    'key': 'fake_key',
                                                    RECIPE: {INGREDIENTS: [{ID: p_id}]}
                                                },
                                                self._managers[m_id][DATA])
                                            eng.set_la(la)
                                            la.set_ingridient(p_data[TYPE], p_id, eng)
                                            self._managers[m_id][PROVIDERS][p_data[ID]].set_enginery(eng)
                                            eng.set_provider(self._managers[m_id][PROVIDERS][p_id])
                                        for eng in self._managers[m_id][PROVIDERS][p_data[ID]].engs:
                                            eng.set_la(la)
                                            la.set_ingridient(p_data[TYPE], p_id, eng)
                                        break
                            self._lighting_areas[e_data[ID]] = la
            except BaseException as ex:
                logging.exception(ex)
            finally:
                self.on_ready()

    def on_ready(self):
        logging.info('Project({}) loaded'.format(self.id))
        for _la_id, _la in self._lighting_areas.items():
            for topic, jocket in _la.get_info():
                self.publish(topic, jocket, True)

        threading.Thread(target=self.on_queue, daemon=True).start()

        e_addr = ProviderAddress(S_TYPE, self.s_id, '+', funit_type='{}')
        state_topic = TopicState(self.id, e_addr)
        tros3_command_topic = TopicCommandTros3(self.id)
        command_topic = TopicCommand(self.id, entity_addr=EntityAddress(mqtt.EQUIPMENT + '/#'))
        for fut in self.STATE_TOPICS:
            self.subscribe(str(state_topic).format(fut))
        self.subscribe(tros3_command_topic)
        self.subscribe(command_topic)

    def on_tros3_command(self, topic, var):
        res = None
        logging.debug('COMMAND: {}'.format(var))
        assert isinstance(topic, TopicCommandTros3)
        e_id = int(topic.entity_addr.enginery_id)

        if e_id in self._subgineries:
            res = self._subgineries[e_id].on_command(topic, var)

        else:
            for m_id in self._managers:
                if e_id in self._managers[m_id][ENGINERIES]:
                    p_id = self._managers[m_id][ENGINERIES][e_id]
                    recipe = self._managers[m_id][PROVIDERS][p_id]
                    for enginery in recipe.engs:
                        if enginery.id == e_id:
                            res = [enginery.on_command(p_id, topic, var)]
        if res is None:
            raise EngineryNotPresent('Enginery({}) is not present'.format(var.id))

        for _topic, _var in res:
            if isinstance(_topic, TopicCommandTros3):
                self.on_tros3_command(_topic, _var)
            else:
                self.add_to_queue(_topic, _var)
        if not self.update_event.is_set():
            self.update_event.set()
        return

    def on_command(self, topic, jocket):
        logging.debug('COMMAND: {}'.format(jocket))
        assert isinstance(topic, TopicCommand)
        e_id = int(topic.entity_addr.enginery_id)

        try:
            if e_id in self._lighting_areas:
                _la = self._lighting_areas[e_id]
                res = _la.on_command(None, topic, jocket)
                for new_topic, new_jocket in res:
                    self.add_to_queue(new_topic, new_jocket)
                if not self.update_event.is_set():
                    self.update_event.set()
            else:
                raise JocketError('объект({}) не найден!'.format(jocket.id), topic=topic, jocket=jocket)
        except JocketError as ex:
            to_topic = mqtt.TopicReply(self.id, topic.session_id)
            if 'data' in jocket.data:
                jocket.data.pop('data')
            jocket.action = spread_core.mqtt.variables.STATE
            jocket.data[spread_core.mqtt.variables.ERROR] = dict(code=123, message='{}'.format(ex))
            self.publish(to_topic, jocket, False)

    def on_state(self, topic, jocket):
        m_id = int(topic.entity_addr.manager_id)
        if m_id in self._managers:
            p_id = int(topic.entity_addr.provider_id)
            if p_id is not None and p_id in self._managers[m_id][PROVIDERS]:
                for eng in self._managers[m_id][PROVIDERS][p_id].engs:
                    arr = eng.on_state(topic, jocket)
                    for to_topic, var in arr:
                        self.add_to_queue(to_topic, var)

            if not self.update_event.is_set():
                self.update_event.set()
        else:
            raise ProviderNotPresent(topic.entity_addr.provider_type, jocket.id)

    def on_event(self, topic, jocket):
        if jocket.invalid:
            return

        m_id = int(topic.entity_addr.manager_id)
        p_id = int(topic.entity_addr.provider_id)
        if m_id in self._managers:
            res = []
            for la_id, _la in self._lighting_areas.items():
                if p_id is not None and p_id in _la.luminosities:
                    res += _la.on_luminosity_event(jocket)
                    # break

                elif p_id is not None and p_id in _la.presences:
                    res += _la.on_presence_event(jocket)
                    # break

            for _topic, _jocket in res:
                self.add_to_queue(_topic, _jocket)

            if not self.update_event.is_set():
                self.update_event.set()
        else:
            raise ProviderNotPresent(topic.entity_addr.provider_type, jocket.id)

    def add_to_queue(self, topic, var):
        if isinstance(topic, TopicCommandTros3):
            self.on_tros3_command(topic, var)
        else:
            # arr = [str(var.id), str(var.cl)]
            # if isinstance(topic, mqtt.TopicReply):
            #     arr.insert(0, var.key)
            # queue[':'.join(arr)] = (topic, var)
            self._queue.append((topic, var))

    def on_queue(self):
        while self._stopped is False:
            self.update_event.wait()
            while len(self._queue) > 0 and self._stopped is False:
                try:
                    topic, jocket = self._queue.pop(0)
                    retain = False if isinstance(topic, TopicCommand) else True
                    self.publish(topic, jocket, retain)
                except BaseException as ex:
                    logging.exception(ex)
            self.update_event.clear()

    def on_exit(self):
        self._stopped = True
        for m_id in self._managers:
            for p_id, e_list in self._managers[m_id][PROVIDERS].items():
                for eng in e_list.engs:
                    for topic, var in eng.set_invalid():
                        try:
                            self.publish(topic, var, True)
                        except BaseException as ex:
                            logging.exception(ex)
        for l_id, la in self._lighting_areas.items():
            for topic, var in la.set_invalid():
                self.publish(topic, var, True)
