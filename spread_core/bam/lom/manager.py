import json
from time import sleep

import lom
from spread_core import mqtt
from spread_core.errors.project_errors import ProjectError, InitError, ClassifierError, ProviderNotPresent
from spread_core.mqtt import spread, TopicCommand, ProviderAddress
from spread_core.mqtt.variables import SET, FUNC
from spread_core.tools.settings import logging, config, PROFILES as SETT_PROFILES, TEMP_DIMMING_PERIOD
from ...bam.managers import Manager, COMMAND

RETAINED = [lom.const.PROFILES]


class Lom(Manager):
    def __init__(self, p_id, m_id):
        super().__init__(p_id, m_id)
        self.devices = {}
        self.profiles = {}
        self.mc = None
        self.def_period = config[TEMP_DIMMING_PERIOD]

    def parse(self, data):
        super(Lom, self).parse(data)
        try:
            broker = data['attributes']['broker']
            interface_conf = dict(
                host=broker['host'],
                port=broker['port'],
                login=broker['login'],
                pwd=broker['pwd'],
                send_topic=broker['downLink'],
                dump_topic=broker['upLink']
            )
            if self.send_interface:
                self.send_interface.set_config(**interface_conf)
        except KeyError:
            raise ProjectError(f'Некорректная конфигурация для менеджера {self}')

        self.read_profiles()

    @property
    def retained(self):
        return super(Lom, self).retained + RETAINED

    def _publish_profiles(self, write=True):
        arr = {}
        for profile in self.profiles.values():
            arr[profile.id] = profile.serialize()
        self.on_update(lom.const.PROFILES, arr)
        if write:
            open(config[SETT_PROFILES], 'w').write(json.dumps(self.get_value(lom.const.PROFILES), indent=4))

    def read_profiles(self):
        self.profiles = {}
        try:
            data = open(config[SETT_PROFILES], 'r').read()
            profiles = json.loads(data)
        except KeyError:
            raise InitError('Profiles file not set! Break!')
        except FileNotFoundError:
            logging.warning('Profiles file not exit! Create new')
        else:
            try:
                for profile_id, profile_data in profiles.items():
                    if isinstance(profile_id, str) and profile_id.isdigit():
                        profile_id = int(profile_id)
                    self.profiles[profile_id] = lom.profiles.GlobalDimmingProfile.deserialize(profile_data)
            except BaseException as ex:
                raise InitError('Ошибка парсинга профилей: ' + str(ex))
            self._publish_profiles(write=False)

    def add_profile(self, profile: lom.profiles.GlobalDimmingProfile):
        need_update = False
        if profile.id not in self.profiles:
            self.profiles[profile.id] = profile
            need_update = True
        else:
            items = self.profiles[profile.id].items
            for item in profile.items:
                if item not in items:
                    self.profiles[profile.id].add_item(item)
                    need_update = True
        if need_update:
            self._publish_profiles()

    def add_provider(self, data, manager):
        super(Lom, self).add_provider(data, manager)
        provider = self._providers[data['id']]
        self.devices[provider.dev_eui] = provider
        if provider.is_broadcast:
            self.mc = provider

    def on_project_ready(self):
        self.on_ready()

    def on_ready(self):
        self.send_interface.start()
        while self.send_interface.ready is False:
            sleep(1)
        super(Lom, self).on_ready()
        self.unsubscribe(mqtt.TopicCommand(self.project_id, entity_addr=mqtt.ManagerAddress.of(entity=self)))
        self.subscribe(spread.topic.Set(spread.address.ManagerAddress.of(self)))
        self.subscribe(
            TopicCommand(
                self.project_id,
                entity_addr=ProviderAddress(
                    mqtt.S_TYPE, self._server_id, self.__class__.__name__,
                    self.id, 'AirBitStreetLamp', '+',
                    lom.const.BRIGHTNESS_LEVEL)
            )
        )

    def on_external_command(self, command):
        try:
            if command.dev_eui in self.devices:
                # logging.debug(f'<- {command}')
                provider = self.devices[command.dev_eui]
                provider.on_command_sended(command)
        except lom.errors.UnknownProfile as ex:
            logging.error(ex)
        except BaseException as ex:
            logging.exception(ex)

    def on_event(self, event):
        try:
            if event.dev_eui in self.devices:
                logging.debug(f'<- {event}')
                provider = self.devices[event.dev_eui]
                for funit_type, data in event.value.items():
                    provider.on_update(funit_type, data)

                if isinstance(event, lom.commands.LomStatusOrdinary):
                    provider.update_position(event)

        except lom.errors.UnknownProfile as ex:
            logging.error(ex)
        except BaseException as ex:
            logging.exception(ex)

    def on_command(self, topic: spread.topic.SpreadTopic, jocket: spread.variable.Variable):
        self.log_command(topic, jocket)
        if self._stopped:
            logging.warning('Manager on scan/extend/construct. Reject command!')
            return
        elif isinstance(topic.entity_address, spread.address.ManagerAddress):
            if isinstance(topic, spread.topic.Set):
                if SET in self.get_funit(topic.entity_address.funit_type):
                    getattr(self, self.get_funit(topic.entity_address.funit_type)[SET][FUNC])(jocket)
                else:
                    raise ClassifierError.of_action(SET, self.__class__.__name__)
        elif isinstance(topic.entity_address, spread.address.ProviderAddress):
            if topic.entity_address.id in self.providers:
                self.providers[topic.entity_address.id].on_command(topic, jocket)
            else:
                raise ProviderNotPresent(topic.entity_address.type, topic.entity_address.id)

        if not self._step_event.is_set():
            self._step_event.set()

    def log_command(self, topic, variable):
        logging.info(f'COMMAND {topic.__class__.__name__}: {topic.entity_address.funit_type} {variable.value}; '
                     f'STACK size = {len(self.actions[COMMAND])}')

    def on_update(self, funit_type, value):
        old_val = self.get_value(funit_type, None)
        if old_val != value:
            self.set_value(funit_type, value)
            self.publish_value(funit_type, value)

    def publish_value(self, funit_type, response, retain=True, invalid=False):
        _addr = self.get_address(funit_type)
        _topic = spread.topic.State(_addr)
        _jocket = spread.variable.Variable(response)
        self.publish(topic=_topic, data=_jocket, retain=retain)

    def SetProfiles(self, variable: spread.variable.Variable):
        need_update = False
        for _id, _data in variable.value.items():
            if isinstance(_id, str) and _id.isdigit():
                _id = int(_id)
            if _data is None:
                if _id in self.profiles:
                    self.profiles.pop(_id)
                    need_update = True
                    if self.mc:
                        self.add_command(self.mc, lom.commands.ClearProfile(self.mc.dev_eui, _id))
            else:
                try:
                    profile = lom.profiles.GlobalDimmingProfile.deserialize(_data)
                    if profile.id not in self.profiles or profile != self.profiles[profile.id]:
                        self.profiles[_id] = profile
                        need_update = True
                except BaseException as ex:
                    raise lom.errors.ParameterError(f'<<{_data}>>: {ex}')

        if need_update:
            self._publish_profiles()
