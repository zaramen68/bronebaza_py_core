import json
import threading

import spread_core.mqtt
from lom.commands import LCommand
from spread_core.bam import generator as generator
from spread_core.bam.dali import F_READY, STATE_C_LEVEL_RAW, F_ON
from spread_core.bam.entities import Entity
from spread_core.bam.multi_command import MultiCommand
from spread_core.errors.project_errors import ProjectError, JocketError, InvalidDevice
from spread_core.mqtt import *
from spread_core.mqtt.variables import DATA, ERROR, VariableJocket
from spread_core.protocols.dali.command import Command
from spread_core.protocols.dali.exceptions import CommandGenerateError
from spread_core.protocols.mercury.commands import MCommand
from spread_core.tools.manager_interface import ManagerOfBroker
from spread_core.tools.settings import logging, set_dump

SURVEY = 0
INFO = 1
COMMAND = 2

RETAINED = [F_READY]


class Manager(Entity, ManagerOfBroker):
    send_interface = None
    _server_id = None
    _name = None
    _key = None
    _bus_id = None
    _pollRate = None
    _survey_timer = None
    _survey_event = threading.Event()
    _step_event = threading.Event()
    _event = threading.Event()
    _external_cmd = threading.Event()

    def __init__(self, p_id,  m_id):
        Entity.__init__(self, m_id)
        self._stopped = False
        self._providers = dict()
        self._addresses = dict()
        self._subgineries = dict()
        self._engineries = dict()
        self.project_id = p_id
        self.actions = {COMMAND: [], INFO: [], SURVEY: []}
        self.ready_timer = None

    @property
    def retained(self):
        return RETAINED

    @property
    def providers(self):
        """returns copy of providers"""
        return self._providers.copy()

    @property
    def addresses(self):
        """returns copy of addresses"""
        return self._addresses.copy()

    def set_addresses(self, address: int, participants: list):
        """set participants of address"""
        if isinstance(participants, (list, tuple)):
            self._addresses[address] = list(participants)

    def parse(self, data):
        self._key = data['key']
        self._server_id = data['serverID']
        self._pollRate = data['attributes']['pollRate']
        self.SetReady(None, False)

    def set_dump(self, provider, key, value):
        set_dump(provider, key, value)

    def set_broker(self, mqttc, send_interface):
        ManagerOfBroker.__init__(self, mqttc)
        send_interface.set_event_handler(self._event)
        send_interface.set_external_cmd_handler(self._external_cmd)
        self.send_interface = send_interface

    def start(self):
        self.subscribe(TopicProject(self.project_id, 'managers.json'))

    def on_state(self, topic, jocket):
        if topic is not None:
            if jocket is not None:
                jocket = VariableJocket(json.loads(jocket))
                if self.ready_timer:
                    self.ready_timer.cancel()
                if isinstance(topic.entity_addr, ProviderAddress):
                    if topic.entity_addr.funit_type != STATE_C_LEVEL_RAW and topic.entity_addr.funit_type != F_ON:
                        _p_id = topic.entity_addr.provider_id
                        if (isinstance(_p_id, int) or str.isdigit(_p_id)) and int(_p_id) in self._providers:
                            if jocket.invalid is False:
                                logging.debug('SET for {} {}: {}'.format(_p_id, topic.entity_addr.funit_type, jocket.value))
                                self._providers[int(_p_id)].on_state(topic.entity_addr.funit_type, jocket.value)
        self.ready_timer = threading.Timer(1, self.on_ready)
        self.ready_timer.setName('on_ready Timer')
        self.ready_timer.start()

    def on_project(self, topic, data):
        self.unsubscribe(topic, False)
        payload = json.loads(data)
        if 'managers' in payload:
            for item in payload['managers']:
                if item['id'] == self.id:
                    self.parse(item)
                    self.subscribe(TopicProject(self.project_id, 'providers.json'), True)
                    return
            raise ProjectError("В файле 'managers.json' отсутствует менеджер с ID={}".format(self.id))
        elif 'providers' in payload:
            for item in payload['providers']:
                if item['managerID'] == self.id:
                    self.add_provider(item, self)
            logging.info('Project({}) loaded'.format(self.project_id))
            self.on_project_ready()

    def on_project_ready(self):
        self.on_state(None, None)
        self.subscribe(TopicState(self.project_id, self.get_address(None)), True)

    def add_provider(self, data, manager):
        provider = generator.generate_provider(data)
        provider.set_manager(manager)
        self._providers[provider.id] = provider

    def on_ready(self):
        self.unsubscribe(TopicState(self.project_id, self.get_address(None)))
        self.subscribe(TopicCommand(self.project_id, entity_addr=ManagerAddress.of(entity=self)))
        threading.Thread(target=self.info, name='InfoThread').start()

    def on_exit(self):
        self.SetReady(None, False)

        self.send_interface.set_stopped()

        self._stopped = True
        self.actions = {0: [], 1: [], 2: []}

        for p_id in self._providers:
            provider = self._providers[p_id]
            provider.on_exit()

        if self._survey_timer:
            self._survey_timer.cancel()
        self._survey_event.set()
        self._step_event.set()
        self._event.set()
        self._external_cmd.set()

    def survey(self):
        while self._stopped is False:
            self._survey_event.wait()
            if len(self.actions[SURVEY]) == 0:
                for p_id in self._providers:
                    provider = self._providers[p_id]
                    if provider.surveyable:
                        provider.on_survey()
            if not self._step_event.is_set():
                self._step_event.set()
            self._survey_event.clear()
            if self._stopped is False:
                self._survey_timer = threading.Timer(interval=self._pollRate / 1000, function=self.dispatch_survey)
                self._survey_timer.setName('dispatch_survey Timer')
                self._survey_timer.start()

    def dispatch_survey(self):
        if not self._survey_event.is_set():
            self._survey_event.set()

    def external_command_handler(self):
        while self._stopped is False:
            command_frame = self.send_interface.get_ex_cmd()
            if command_frame:
                try:
                    self.on_external_command(command_frame)
                except BaseException as ex:
                    logging.debug(f'EXTERNAL FRAME ERROR[{command_frame}]')
                    logging.exception(ex)
            else:
                self._external_cmd.clear()
                self._external_cmd.wait()

    def on_external_command(self, command_frame):
        raise NotImplementedError()

    def event_handler(self):
        while not self._stopped:
            event = self.send_interface.get_event()
            if event:
                try:
                    self.on_event(event)
                except BaseException as ex:
                    logging.debug(f'EVENT FRAME ERROR[{event}]')
                    logging.exception(ex)

            else:
                self._event.clear()
                self._event.wait()

    def on_event(self, event):
        raise NotImplementedError()

    def info(self):
        for p_id in self._providers:
            if self._stopped:
                return
            provider = self._providers[p_id]
            if provider.infoble:
                try:
                    provider.get_bindings()
                    provider.check_valid()
                    if provider.is_valid:
                        provider.get_info()
                        provider.override_info()
                except InvalidDevice as ex:
                    logging.warning(ex)
                    provider.set_valid(False)

        threading.Thread(target=self.survey, name='SurveyThread').start()
        threading.Thread(target=self.do_next, name='DoNextThread').start()
        threading.Thread(target=self.external_command_handler, name='ExternalThread').start()
        threading.Thread(target=self.event_handler, name='EventThread').start()
        self._survey_event.set()
        self.SetReady(None, True)

    def do_next(self):
        while self._stopped is False:
            self._step_event.wait()

            while self._stopped is False:
                _priority = None
                for _priority, arr in self.actions.items():
                    if len(arr) > 0:
                        provider, cmd = arr.pop(0)

                        if isinstance(cmd, MultiCommand):
                            try:
                                cmd.call()
                            except BaseException as ex:
                                logging.exception(ex)
                                # to_topic = TopicReply(self.project_id, cmd.session_id)
                                # funit = provider.get_funit(cmd.funit_type)
                                # jocket = VariableJocket.create_data(id=provider.id, cl=funit['id'],
                                #                                     val=provider.get_value(cmd.funit_type),
                                #                                     action=mqtt.variables.STATE, key=cmd.key)
                                # if DATA in jocket.data:
                                #     jocket.data.pop(DATA)
                                # jocket.data[ERROR] = dict(code=123, message='{}'.format(ex))
                                # self.publish(to_topic, jocket.pack())
                        elif isinstance(cmd, (Command, MCommand)):
                            try:
                                if provider:
                                    provider.request(cmd)
                                else:
                                    self.send_interface.send(cmd)
                            except BaseException as ex:
                                logging.exception(ex)
                        elif isinstance(cmd, LCommand):
                            try:
                                if provider:
                                    provider.request(cmd, mc=not provider.is_device)
                                else:
                                    self.send_interface.send(cmd, mc=not provider.is_device)
                            except BaseException as ex:
                                logging.exception(ex)
                        else:
                            logging.warning('unknown command: {}'.format(cmd))
                        break

                if _priority == SURVEY:
                    break

            self._step_event.clear()

    def add_command(self, provider, *cmds):
        if not self._stopped:
            for cmd in cmds:
                if cmd:
                    self.actions[COMMAND].append((provider, cmd))
                else:
                    logging.warning('Empty command')

            if not self._step_event.is_set():
                self._step_event.set()

    def add_info(self, provider, cmd):
        if self._stopped:
            return
        if (provider, cmd) not in self.actions[INFO]:
            self.actions[INFO].append((provider, cmd))

    def add_survey(self, provider, cmd):
        if self._stopped:
            return
        if (provider, cmd) not in self.actions[SURVEY]:
            self.actions[SURVEY].append((provider, cmd))

    def on_command(self, topic, jocket):
        self.log_command(topic, jocket)
        if self._stopped:
            logging.warning('Manager on scan/extend/construct. Reject command!')
            return
        try:
            if jocket.id == self.id:
                act = jocket.action
                funit = topic.entity_addr.funit
                if act in funit:
                    if 'func' in funit[jocket.action] and funit[jocket.action]['func'] in dir(self):
                        cmd = MultiCommand(topic.entity_addr.funit_type, getattr(self, funit[jocket.action]['func']), jocket.data[DATA])
                        cmd.set_signature(jocket.key, topic.session_id)
                        self.add_command(self, cmd)
                    else:
                        raise JocketError(
                            '<<{}>> is not implemented in classifier for <<{}>>!'.format(act, self.__class__.__name__))
                else:
                    raise JocketError(
                        '<<{}>>  of <<{}>> is not present in <<{}>>!'.format(act, topic.entity_addr.funit_type,
                                                                             self.__class__.__name__))
            elif jocket.id in self._providers:
                provider = self._providers[jocket.id]
                if not provider.is_valid and jocket.action != spread_core.mqtt.variables.GET and 'Binding' not in topic.entity_addr.funit_type:
                    raise CommandGenerateError('device is invalid!')
                provider.on_command(topic, jocket)
            else:
                topic = TopicReply(self.project_id, topic.session_id)
                if 'data' in jocket.data:
                    jocket.data.pop('data')
                jocket.action = spread_core.mqtt.variables.STATE
                jocket.data['error'] = dict(code=123, message='object {} not present in bam'.format(jocket.id))
                self.publish(topic, jocket.pack())
                raise JocketError('объект с адресом {} не найден!'.format(jocket.id), topic=topic, jocket=jocket)
        except (JocketError, CommandGenerateError) as ex:
            to_topic = TopicReply(self.project_id, topic.session_id)
            if 'data' in jocket.data:
                jocket.data.pop('data')
            jocket.action = spread_core.mqtt.variables.STATE
            jocket.data[ERROR] = dict(code=123, message='{}'.format(ex))
            self.publish(to_topic, jocket.pack())

        if not self._step_event.is_set():
            self._step_event.set()

    def log_command(self, topic, jocket):
        set_params = '= {}'.format(jocket.value) if jocket.action == spread_core.mqtt.variables.SET else ''
        logging.info(f'COMMAND {jocket.id}: {jocket.action} {topic.entity_addr.funit_type} {set_params}; '
                     f'session_id = {topic.session_id}; '
                     f'STACK size = {len(self.actions[COMMAND])}')

    def SetReady(self, sig, value):
        self.on_update(F_READY, value)

    def get_funit(self, funit_type):
        if self.__class__.__name__ in mqtt.classifier:
            if funit_type in mqtt.classifier[self.__class__.__name__]:
                return mqtt.classifier[self.__class__.__name__][funit_type]
        return None

    def get_address(self, funit_id):
        if funit_id is not None:
            return ManagerAddress.of(self, funit_id)
        return ManagerAddress.of(self)

    def on_update(self, funit_type, value):
        _addr = self.get_address(funit_type)
        _topic = TopicState(self.project_id, _addr)
        _jocket = VariableJocket.create_data(self.id, _addr.funit['id'], spread_core.mqtt.variables.STATE, val=value)
        self.publish(topic=_topic, data=_jocket.pack(), retain=funit_type in self.retained)
