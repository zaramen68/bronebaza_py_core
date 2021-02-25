import datetime
import threading

import lom
from spread_core.bam.multi_command import MultiCommand
from spread_core.bam.providers import Provider
from spread_core.errors.project_errors import JocketError, ClassifierError, CommandError
from spread_core.mqtt import spread, mqtt, variables
from spread_core.tools import settings


class AirBitStreetLamp(Provider):
    _dumped = [lom.const.PERSONAL_PROFILE]

    def __init__(self, data):
        super(AirBitStreetLamp, self).__init__(data)
        self.dev_eui = data['attributes']['dev_eui']
        self.binding = data['attributes']['binding']
        self._current_profile = None
        self._level = None
        self.timer = None

    @property
    def profile(self):
        return self._current_profile

    @profile.setter
    def profile(self, profile: lom.profiles.DimmingProfile):
        if profile is None:
            profile = lom.profiles.GlobalGeoProfile.default()
        if self._current_profile != profile:
            self._current_profile = profile
            self.on_update(lom.const.CURRENT_PROFILE, profile.serialize())
            profile.set_position(self.get_value(lom.const.LATITUDE, 0), self.get_value(lom.const.LONGITUDE, 0), self.get_value(lom.const.ALTITUDE, 0))
            self.on_timer()

    def on_timer(self):
        profile = self.profile

        if self.timer:
            self.timer.cancel()
            self.timer = None

        if isinstance(profile, lom.profiles.DimmingProfile):
            items = profile.items
            if len(items) > 0:
                if isinstance(profile, lom.profiles.TimedLevelProfile):
                    if profile.start_time.timestamp() + items[0].period <= datetime.datetime.now().timestamp():
                        self.apply_profile(self.get_value(lom.const.ACTIVE_PROFILE, 0))
                    else:
                        self.level = items[0].value
                        self.start_timer(items[0].period)
                # elif isinstance(profile, lom.profiles.LumProfile):
                #     if self.get_value(lom.const.ILLUMINATION, -1) == profile.
                #     self.brightness_level
                elif profile.is_timed:
                    self.level = items[-1].value
                    self.start_timer(items[0].time_left)

    def on_lum(self, lum):
        if isinstance(self.profile, lom.profiles.LumProfile):
            last = None
            for item in self.profile.items:
                if last is None:
                    last = item

                if lum >= item.lum:
                    last = item
                elif last:
                    break

            if last:
                self.level = last.value

    def start_timer(self, time):
        self.stop_timer()
        self.timer = threading.Timer(time, self.on_timer)
        self.timer.start()
        print('Start timer after {}'.format(datetime.timedelta(seconds=time)))

    def stop_timer(self):
        if self.timer:
            self.timer.cancel()
            self.timer = None

    @property
    def level(self):
        return self._level

    @level.setter
    def level(self, level: int):
        if level != self._level:
            if level is None:
                level = self._level
                if level is None:
                    level = 0
                invalid = True
            else:
                self._level = level
                invalid = False

            if level != 0:
                brightness = max(1, min(100, round(100 * level / 254)))
            else:
                brightness = 0

            state_topic = mqtt.TopicState(self._manager.project_id, mqtt.ProviderAddress.of(self, lom.const.BRIGHTNESS_LEVEL))
            self._manager.publish(state_topic, variables.VariableJocket.create_data(self.id, 0, mqtt.STATE, brightness, invalid=invalid))

    @property
    def infoble(self):
        return self.is_device

    @property
    def is_device(self):
        return self.binding == lom.const.DEVICE

    @property
    def is_broadcast(self):
        return self.binding == lom.const.MULTICAST

    @property
    def is_group(self):
        return self.binding == lom.const.GROUP

    def get_bindings(self):
        self.on_update(lom.const.BINDING, self.binding)
        self.on_update(lom.const.DEV_EUI, self.dev_eui)

    def on_update(self, funit_type, value, retain=True, invalid=False):
        old_val = self.get_value(funit_type, None)
        if old_val != value:
            self.set_value(funit_type, value)
            self.publish_value(funit_type, value)

        if funit_type == lom.const.ACTIVE_PROFILE:
            if not isinstance(self.profile, (lom.profiles.TimedLevelProfile, lom.profiles.PersonalDimmingProfile)):
                if self.profile is None or self.profile.id != value:
                    self.apply_profile(value)
        elif funit_type == lom.const.PERSONAL_PROFILE:
            profile = lom.profiles.PersonalDimmingProfile.deserialize(value)
            self.profile = profile
        elif funit_type == lom.const.ILLUMINATION:
            self.on_lum(value)

        # if funit_type == lom.const.EXTRA_FLAGS:
        #     c277 = 10 if self.get_value(lom.const.ANSWER_RAND_INTERVAL) != 10 else 15
        #     self.send(lom.commands.SetConfig(self.dev_eui, [lom.const.ANSWER_RAND_INTERVAL, c277]))

    def update_position(self, event: lom.commands.LomStatusOrdinary):
        if self.profile and isinstance(self.profile, lom.profiles.DimmingProfile):
            has_changed = self.profile.set_position(
                event.value[lom.const.LATITUDE],
                event.value[lom.const.LONGITUDE],
                event.value[lom.const.ALTITUDE])
            if has_changed:
                self.on_timer()

    def apply_profile(self, profile_id):
        if profile_id == 0:
            self.profile = None
        elif profile_id in self.manager.profiles:
            self.profile = self.manager.profiles[profile_id]
        else:
            raise lom.errors.UnknownProfile(profile_id)

    def on_command(self, topic: spread.topic.SpreadTopic, jocket: spread.variable.Variable):
        err_args = [self.manager.__class__.__name__, self.__class__.__name__]
        if not self.is_valid and isinstance(topic, spread.topic.Set) and 'Binding' not in topic.entity_address.funit_type:
            raise JocketError('device is invalid!')
        funit = self.get_funit(topic.entity_address.funit_type)
        if funit:
            if isinstance(topic, spread.topic.Set):
                action = 'set'
                if action not in funit:
                    raise ClassifierError.of_action(action, *err_args)
                else:
                    if 'cmd' in funit[action]:
                        cmd = funit[action]['cmd']
                        if jocket.value is None:
                            cmd = cmd(self.dev_eui)
                        elif isinstance(jocket.value, dict):
                            cmd = cmd(self.dev_eui, **jocket.value)
                        elif isinstance(jocket.value, (list, tuple)):
                            cmd = cmd(self.dev_eui, *jocket.value)
                        else:
                            try:
                                cmd = cmd(self.dev_eui, jocket.value)
                            except CommandError as ex:
                                raise ex
                            except BaseException as ex:
                                raise CommandError.of_exec(str(ex))
                    elif 'func' in funit[action]:
                        func = funit[action]['func']
                        if hasattr(self, func) and callable(getattr(self, func)):
                            try:
                                cmd = MultiCommand(topic.entity_address.funit_type, getattr(self, func), jocket.value)
                            except CommandError as ex:
                                raise ex
                            except BaseException as ex:
                                raise CommandError.of_exec(str(ex))
                        else:
                            raise ClassifierError.action_of_func(func, *err_args)
                    else:
                        raise ClassifierError.no_action_type(action, *err_args)

                    self.manager.add_command(self, cmd)
        else:
            raise ClassifierError.of_funit(topic.entity_address.funit_type, *err_args)

    def on_command_sended(self, cmd):
        if isinstance(cmd, lom.commands.SetConfig):
            self._manager.add_info(self, lom.commands.GetConfig(self.dev_eui, [i[0] for i in cmd.items]))
        elif isinstance(cmd, lom.commands.ClearProfile):
            if self.get_value(lom.const.ACTIVE_PROFILE) in cmd.ids:
                self.on_update(lom.const.ACTIVE_PROFILE, 0)
                if self.profile and self.profile.id in cmd.ids:
                    self.profile = None
        elif isinstance(cmd, lom.commands.SetProfile):
            if isinstance(cmd.profile, lom.profiles.TimedLevelProfile):
                self.profile = cmd.profile
            elif isinstance(cmd.profile, lom.profiles.GlobalDimmingProfile):
                self.manager.add_profile(cmd.profile)
                self.profile = self.manager.profiles[cmd.profile.id]

    def on_survey(self):
        pass

    def on_exit(self):
        self.level = None
        self.stop_timer()

        for funit_type in self.values:
            self.publish_value(funit_type, None)

    def get_info(self):
        self._manager.add_info(self, lom.commands.GetConfig(self.dev_eui, list(lom.const.CONFIGURATION.keys())))

    def publish_value(self, funit_type, response, retain=True, invalid=False):
        topic = spread.topic.State(self.get_address(funit_type))
        var = spread.variable.Variable(response)
        self.manager.publish(topic, var, retain)

    def get_address(self, funit_id):
        return spread.address.ProviderAddress.of(self, funit_id)

    def override_info(self):
        for funit_type, value in settings.get_dump_entity(self).items():
            self.on_update(funit_type, value)

    def get_value(self, funit_type, def_value=None):
        if funit_type in self.values:
            return self.values[funit_type]
        if def_value is not None:
            return def_value
        return None

    def SetBrightnessLevel(self, sig, brightness):
        if brightness != 0:
            level = min(max(1, int(254 * brightness / 100)), 254)
        else:
            level = 0
        item = lom.profiles.profile_items.TimedLevel(level, self.manager.def_period)
        profile = lom.profiles.GlobalTimedLevel.of_level(item)
        self.manager.add_command(self, lom.commands.GlobalTimedLevel(self.dev_eui, profile))

    def SetCurrentProfile(self, sig, value: (int, dict)):
        if isinstance(value, dict):
            """Personal profile"""
            raise CommandError.of_exec('Персональный профиль не реализлован!')
        else:
            """Global profile"""
            try:
                profile = self.manager.profiles[int(value)]
            except KeyError:
                raise CommandError.of_exec('Идентификатор {} отсутствует в списке профилей!'.format(value))

        if not isinstance(profile, lom.profiles.TimedLevelProfile):
            self.manager.add_command(self, lom.commands.ClearAllProfiles(self.dev_eui))
        self.manager.add_command(self, lom.commands.SetProfile.of(self.dev_eui, profile))
        self.manager.add_command(self, lom.commands.SetConfig(self.dev_eui, [lom.const.ACTIVE_PROFILE, profile.id]))
