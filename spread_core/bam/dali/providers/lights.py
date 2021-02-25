import json
import logging
import threading

import math

from spread_core.bam.dali import *
from spread_core.bam.dali import scanner, bindings
from spread_core.bam.dali.providers.providers import RapidaDaliProvider
from spread_core.bam.dali.tuner_limited import TunerLimited
from spread_core.bam.multi_command import MultiCommand
from spread_core.mqtt import LINEAR_CURVE
from spread_core.protocols.dali.address import Short
from spread_core.protocols.dali.exceptions import CommandGenerateError
from spread_core.protocols.dali.gear import general as gear, led as led, colour_control as cc
from spread_core.tools import utils

""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
"""                                  DALI 1                                """
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

DISCOVERY_DELAY = 0.5


class RapidaDaliLight(RapidaDaliProvider):
    _dali_type = 1

    def __init__(self, data):
        super(RapidaDaliLight, self).__init__(data)
        self.fadeTime = 2
        self.fadeRate = None
        self._level_timer = None
        self.is_unaddress_tunned = False
        self._tuner = None
        self.level_cmd_count = 0

    @property
    def tuner(self):
        return self._tuner

    def _apply_cmd(self, cmd, *args):
        if cmd._hasparam:
            return cmd(self.short_addr, *args)
        return cmd(self.short_addr)

    def on_survey(self):
        super(RapidaDaliLight, self).on_survey()
        if F_SERIAL_MIN in self.values:
            return

        self.manager.add_survey(self, gear.QueryStatus(self.short_addr.address))
        self.manager.add_survey(self, gear.QueryActualLevel(self.short_addr.address))

    def request(self, cmd):
        super(RapidaDaliLight, self).request(cmd)

        if cmd.is_send_notify:
            self.on_command_sended(cmd)

    def check_valid(self):
        super(RapidaDaliLight, self).check_valid()
        if self.is_device:
            cmd = gear.QueryStatus(self.short_addr.address)
            status = self.manager.send_interface.send(cmd)
            self.on_update(cmd.funit_type[0], status)

    def on_group_updated(self, funit_type, value, sig=None):
        if not self.is_device:
            for _p_id in self.get_members():
                _provider = self.manager.providers[_p_id]
                if isinstance(_provider, RapidaDaliLight) and _provider.is_device:
                    _provider._generate_def_value(funit_type, value, sig=sig)

    def get_info(self):
        if self.is_device:
            super(RapidaDaliLight, self).get_info()
            self.request(gear.QueryMinLevel(self.short_addr.address))
            self.request(gear.QueryMaxLevel(self.short_addr.address))
            self.request(led.QueryDimmingCurve(self.short_addr.address))
            self.request(gear.QueryActualLevel(self.short_addr.address))
            self.request(gear.QueryDeviceType(self.short_addr.address))
            self.request(gear.QueryFadeTimeFadeRate(self.short_addr.address))
            self.manager.add_info(self, gear.QueryPowerOnLevel(self.short_addr.address))
            self.manager.add_info(self, gear.QuerySystemFailureLevel(self.short_addr.address))
            self.manager.add_info(self, gear.QueryPhysicalMinimum(self.short_addr.address))
            self.manager.add_info(self, MultiCommand(F_SCENE_LEVELS_RAW, self.GetSceneLevelsRaw))
            self.manager.add_info(self, gear.QueryActualLevel(self.short_addr.address))
        else:
            self._generate_def_value(F_FADE_TIME, self.get_value(F_FADE_TIME, None))
            self._generate_def_value(F_FADE_RATE, self.get_value(F_FADE_RATE, None))
            self._generate_def_value(F_MIN_LEVEL_RAW, self.get_value(F_MIN_LEVEL_RAW, 1))
            self._generate_def_value(F_MAX_LEVEL_RAW, self.get_value(F_MAX_LEVEL_RAW, 254))
            self._generate_def_value(F_DIMMING_CURVE, self.get_value(F_DIMMING_CURVE, None))
            self._generate_def_value(STATE_C_LEVEL_RAW, self.get_value(STATE_C_LEVEL_RAW, 0))
            self._generate_def_value(F_POWER_ON_LEVEL_RAW, self.get_value(F_POWER_ON_LEVEL_RAW, 0))
            self._generate_def_value(F_SYSTEM_FAILURE_LEVEL_RAW, self.get_value(F_SYSTEM_FAILURE_LEVEL_RAW, 80))
            self._generate_def_value(F_PHYSICAL_MIN_LEVEL_RAW, self.get_value(F_PHYSICAL_MIN_LEVEL_RAW, 1))
            self._generate_def_value(F_SCENE_LEVELS_RAW, self.get_value(F_SCENE_LEVELS_RAW, None))
            _groups = [{'index': self.binding.addr.group, 'value': True}] if self.is_group else []
            self._generate_def_value(F_GROUPS, self.get_value(F_GROUPS, _groups))
        self._generate_def_value(F_DISCOVERY, self.get_value(F_DISCOVERY, False))

    def on_command_prepared(self, *commands):
        super(RapidaDaliLight, self).on_command_prepared(*commands)
        for command in commands:
            if isinstance(command, gear._GearCommand) and command.is_levels_dependent:
                _p_ids = self.get_members()
                for _p_id in _p_ids:
                    _provider = self.manager.providers[_p_id]
                    if isinstance(_provider, RapidaDaliLight):
                        _provider.stop_level_timer()
                        _provider.level_cmd_count += 1

    def stop_level_timer(self):
        if self._level_timer:
            self._level_timer.cancel()

    def query_level(self, sig):
        if self.get_value(F_DISCOVERY, False) is True:
            return

        if self.is_device:
            self.level_cmd_count -= 1

            if self.level_cmd_count < 1:
                self.level_cmd_count = 0
                cmd = gear.QueryActualLevel(self.short_addr)
                if sig:
                    cmd.sig.set_session_id(sig.session_id)
                    cmd.sig.set_key(sig.key)
                self.stop_level_timer()
                self._level_timer = threading.Timer(1+self.fadeTime, self.on_command_prepared, args=[cmd])
                self._level_timer.setName('Light.query_level Timer')
                self._level_timer.start()
        else:
            for _p_id in self.get_members():
                _provider = self.manager.providers[_p_id]
                if isinstance(_provider, RapidaDaliLight):
                    if _provider.is_device:
                        _provider.query_level(sig)
                    else:
                        logging.warning(f'Provider({_provider.id}) is participant of {self.id}')

    def on_state(self, funit_type, value):
        super(RapidaDaliLight, self).on_state(funit_type, value)

        if funit_type == F_FADE_TIME:
            if 'ft' in value:
                self.fadeTime = 0.1 + int(value.split('ft')[1]) / 10

    def on_update(self, funit_type, response, retain=True, invalid=False):
        invalid = invalid or response.value is None or (hasattr(response.value, 'error') and response.value.error)

        if invalid is False:
            if funit_type == F_FADE_TIME:
                if isinstance(response.value[funit_type], int):
                    self.fadeTime = 0.1 + int(0.5 * (math.sqrt(pow(2, response.value[funit_type]))) * 100) / 100
                else:
                    if hasattr(response.value[funit_type], 'split'):
                        if 'ft' in response.value[funit_type]:
                            self.fadeTime = 0.1 + int(response.value[funit_type].split('ft')[1]) / 10
            elif funit_type == F_FADE_RATE:
                if isinstance(response.value[funit_type], int):
                    self.fadeRate = round(int(506 / (math.sqrt(pow(2, response.value[funit_type]))) * 100) / 100)
                else:
                    if hasattr(response.value[funit_type], 'split'):
                        if 'fr' in response.value[funit_type]:
                            self.fadeRate = 0.1 + int(response.value[funit_type].split('fr')[1]) / 10

        super(RapidaDaliLight, self).on_update(funit_type, response, retain, invalid)

        if funit_type in [STATE_C_LEVEL_RAW, F_DIMMING_CURVE]:
            self.GetBrightnessLevel()

    def prs2raw(self, p):
        if p == 0:
            return p
        _min = self.get_value(F_MIN_LEVEL_RAW, 1)
        _max = self.get_value(F_MAX_LEVEL_RAW, 254)

        if self.get_value(F_DIMMING_CURVE, None) == LINEAR_CURVE:
            return min(max(_min, int(254 * p / 100)), _max)
        else:
            return min(max(_min, int(((math.log10(p) + 1) * 253 / 3 + 1))), _max)

    def raw2prs(self, r):
        if self.get_value(F_DIMMING_CURVE, None) == LINEAR_CURVE:
            return min(100, round(100 * r / 254))
        else:
            if r == 0:
                return 0
            elif r < 1:
                return 1
            else:
                p = 10 ** ((r - 1) * 3 / 253 - 1)
                if 0 < p < 1:
                    p = 1
                return round(p)

    def read_memory_location(self, bank_id, start_address, end_address):
        # return b'\x01'
        return scanner.Bus1.read_memory_location(self.manager.send_interface, self.short_addr.address, bank_id, start_address, end_address)

    def set_dtr_command(self, index, val):
        if index == 0:
            return gear.DTR0(val)
        elif index == 1:
            return gear.DTR1(val)
        elif index == 2:
            return gear.DTR2(val)
        else:
            raise CommandGenerateError('комманды DTR{} не уществует'.format(index))

    def SetShortAddress(self, sig, new_addr):
        _dtr0 = None
        _provider = None
        if new_addr != self.short_addr.address:
            if self.is_device:
                old_short = self.short_addr
                if new_addr is not None:
                    new_short = Short(new_addr)
                    res = self.send(gear.QueryDeviceType(new_short))
                    if res.value is not None:
                        for p_id in self.manager.addresses[new_addr]:
                            _provider = self.manager.providers[p_id]
                            if isinstance(_provider, self.__class__):
                                old_long = []
                                new_long = []

                                self.send(gear.Terminate())

                                self.send(gear.Initialise(broadcast=False, address=old_short.address))
                                self.send(gear.Initialise(broadcast=False, address=new_short.address))

                                old_long.append(self.send(gear.QueryRandomAddressH(old_short)))
                                old_long.append(self.send(gear.QueryRandomAddressM(old_short)))
                                old_long.append(self.send(gear.QueryRandomAddressL(old_short)))

                                new_long.append(self.send(gear.QueryRandomAddressH(new_short)))
                                new_long.append(self.send(gear.QueryRandomAddressM(new_short)))
                                new_long.append(self.send(gear.QueryRandomAddressL(new_short)))

                                self.send(gear.SetSearchAddrH(old_long[0].value.as_integer))
                                self.send(gear.SetSearchAddrM(old_long[1].value.as_integer))
                                self.send(gear.SetSearchAddrL(old_long[2].value.as_integer))
                                self.send(gear.ProgramShortAddress(new_short.address))

                                self.send(gear.SetSearchAddrH(new_long[0].value.as_integer))
                                self.send(gear.SetSearchAddrM(new_long[1].value.as_integer))
                                self.send(gear.SetSearchAddrL(new_long[2].value.as_integer))
                                self.send(gear.ProgramShortAddress(old_short.address))

                                self.send(gear.Terminate())

                                break
                            else:
                                _provider = None
                        else:

                            raise CommandGenerateError('Address({}) is not free'.format(new_addr))
                    else:
                        _dtr0 = gear.DTR0((new_short.address << 1) | 1)

                    if new_addr not in self.manager.addresses:
                        self.manager.set_addresses(new_addr,  [])
                else:
                    _dtr0 = gear.DTR0(0xff)

                if _dtr0 is not None:
                    self.send(_dtr0)
                    self.send(gear.SetShortAddress(old_short))

                if _provider:
                    self.values[F_BINDING_DEVICE] = None
                    _provider.values[F_BINDING_DEVICE] = None

                    _vals = self.values
                    self.values = _provider.values
                    _provider.values = _vals

                    self.SetBindingDevice(sig, old_short.address)
                    self.publish_all(sig)
                    _provider.SetBindingDevice(sig, new_addr)
                    _provider.publish_all(sig)
                else:
                    self.SetBindingDevice(sig, new_addr)

            else:
                raise CommandGenerateError('You can not give an address to {}'.format(self.binding.b_type))

    def SetDiscovery(self, sig, value):
        _discovery = self.get_value(F_DISCOVERY, False)
        if _discovery != value:
            self._generate_def_value(F_DISCOVERY, value, sig=sig)
            if _discovery is False and value is True:
                self.set_discovery_max(sig)

    # def SetDiscoveryHardware(self, sig, value):
    #     _discovery = self.get_value(F_DISCOVERY, False)
    #     if _discovery != value:
    #         self._generate_def_value(F_DISCOVERY, value, sig=sig)
    #         if _discovery is False and value is True:
    #             if self.is_broadcast:
    #                 _broad_cast = True
    #                 _address = None
    #             elif self.is_unaddressed:
    #                 _broad_cast = False
    #                 _address = None
    #             elif self.is_device:
    #                 _broad_cast = False
    #                 _address = self.short_addr.address
    #             else:
    #                 for _p_id in self.get_group_members():
    #                     _provider = self.manager.providers[_p_id]
    #                     if _provider.is_device:
    #                         _provider.SetDiscovery(sig, value)
    #                 return
    #
    #             self.send(gear.Initialise(_broad_cast, _address))
    #             self.send(gear.IdentifyDevice(self.short_addr))
    #             self.send(gear.RecallMaxLevel(self.short_addr))
    #             threading.Timer(11, function=self.check_discovery).start()
    #         else:
    #             self.send(gear.Terminate())
    #             if self.is_group:
    #                 for _p_id in self.get_group_members():
    #                     _provider = self.manager.providers[_p_id]
    #                     if _provider.is_device:
    #                         _provider.SetDiscovery(sig, value)

    def set_discovery_max(self, sig):
        if self.get_value(F_DISCOVERY) is True:
            self.on_command_prepared(gear.RecallMaxLevel(self.short_addr))
            threading.Timer(DISCOVERY_DELAY, function=self.set_discovery_min, args=[sig]).start()
        else:
            self.reset_discovery(sig)

    def set_discovery_min(self, sig):
        if self.get_value(F_DISCOVERY) is True:
            self.on_command_prepared(gear.Off(self.short_addr))
            threading.Timer(DISCOVERY_DELAY, function=self.set_discovery_max, args=[sig]).start()
        else:
            self.reset_discovery(sig)

    def reset_discovery(self, sig):
        self.SetBrightnessLevel(sig, self.get_value(BRIGHTNESS_LEVEL, 0))

    def GetSceneLevelsRaw(self, sig=None):
        if self.is_device:
            _levels = []
            for _scene_index in range(0, 16):
                resp = self.manager.send_interface.send(gear.QuerySceneLevel(self.short_addr, _scene_index))
                if resp is not None and resp.value is not None:# and resp.value.as_integer < 0xff:
                    _levels.append(dict(index=_scene_index, value=resp.value.as_integer))
        else:
            _levels = self.get_value(F_SCENE_LEVELS_RAW)

        self._generate_def_value(F_SCENE_LEVELS_RAW, _levels, sig=sig)

    def SetSceneLevelsRaw(self, sig, val):
        if isinstance(val, str):
            val = json.loads(val)
        _val = dict()
        for item in val:
            _val[item['index']] = item['value']

        c_val = self.get_value(F_SCENE_LEVELS_RAW, dict())
        _c_val = dict()
        for item in c_val:
            _c_val[item['index']] = item['value']

        for _i in range(0, 16):
            _v = None
            if _i in _val:
                if _i not in _c_val or _c_val[_i] != _val[_i]:
                    self.request(gear.DTR0(_val[_i]))
                    self.manager.send_interface.send(gear.SetScene(self.short_addr, _i))
            elif _i in _c_val:
                val.append(dict(index=_i, value=_c_val[_i]))
            else:
                val.append(dict(index=_i, value=0xff))

        self._generate_def_value(F_SCENE_LEVELS_RAW, val, sig=sig)
        self.on_group_updated(F_SCENE_LEVELS_RAW, val, sig)

    def GetGroups(self, sig=None):
        if self.is_device:
            i = self.manager.send_interface
            _groups = []

            resp_0_7 = i.send(gear.QueryGroupsZeroToSeven(self.short_addr))
            if resp_0_7 and resp_0_7.value is not None and not resp_0_7.value.error:
                for _i in range(0, 8):
                    _include = resp_0_7.value.as_integer & (1 << _i) == (1 << _i)
                    _groups.append(dict(index=_i, value=_include))
                    if _include:
                        self.manager.add_to_group(1, _i, self.id)

            resp_8_15 = i.send(gear.QueryGroupsEightToFifteen(self.short_addr))
            if resp_8_15 and resp_8_15.value is not None and not resp_8_15.value.error:
                for _i in range(0, 8):
                    _include = resp_8_15.value.as_integer & (1 << _i) == (1 << _i)
                    _groups.append(dict(index=(8+_i), value=_include))
                    if _include:
                        self.manager.add_to_group(1, 8+_i, self.id)
        else:
            _groups = self.get_value(F_GROUPS, None)

        self._generate_def_value(F_GROUPS, _groups, sig=sig)

    def SetGroups(self, sig, val):
        i = self.manager.send_interface
        if not isinstance(val, list):
            val = json.loads(val)
        _val = dict()
        for item in val:
            _val[item['index']] = item['value']

        c_val = self.get_value(F_GROUPS, dict())
        _c_val = dict()
        for item in c_val:
            _c_val[item['index']] = item['value']

        for _i, _inc in _val.items():
            if _inc is True:
                if _i not in _c_val or _c_val[_i] != _val[_i]:
                    i.send(gear.AddToGroup(self.short_addr, _i))
                    if self.is_device:
                        self.manager.add_to_group(1, _i, self.id)
            elif _i in _c_val and _c_val[_i] is True:
                if self.is_group and self.binding.addr.group == _i:
                    continue
                i.send(gear.RemoveFromGroup(self.short_addr, _i))
                if self.is_device:
                    self.manager.remove_from_group(1, _i, self.id)

            _c_val[_i] = _inc

        res = []
        for _i, _inc in _c_val.items():
            res.append({'index': _i, 'value': _inc})

        self._generate_def_value(F_GROUPS, res, sig=sig)
        self.on_group_updated(F_GROUPS, val, sig)

    def SetGroupLevel(self, sig, value):
        try:
            value = int(value)
        except:
            raise CommandGenerateError('Value({}) must be integer'.format(value))
        else:
            group_ids = self.get_value(F_GROUPS, None)
            group_id = None
            group_size = 999999999
            if group_ids is None:
                self.GetGroups()
                group_ids = self.get_value(F_GROUPS, [])

            for item in group_ids:
                if item['value'] is True and 'index' in item:
                    _group_id = item['index']
                    if _group_id in self.manager._groups_1:
                        _group_size = len(self.manager._groups_1[_group_id])
                        if _group_size < group_size:
                            group_size = _group_size
                            group_id = _group_id

            if group_id is not None:
                _provider = None
                for _p_id, _p in self.manager.providers.items():
                    if isinstance(_p, RapidaDaliLight) and isinstance(_p.binding.addr, bindings.Group) and group_id == _p.binding.addr.group:
                        _provider = _p
                        break
                if _provider is not None:
                    _provider.SetBrightnessLevel(sig, value)
                else:
                    self.set_pause_for_group(group_id)
                    group_addr = bindings.Group(group_id)
                    value = self.prs2raw(value)
                    self.manager.add_command(None, gear.DAPC(group_addr, value))
                    for _p_id in self.manager.get_group_members(self._dali_type, group_id):
                        _participant = self.manager.providers[_p_id]
                        if isinstance(_participant, RapidaDaliLight):
                            _participant.level_cmd_count += 1
                            _participant.query_level(sig)
            else:
                self.SetBrightnessLevel(sig, value)

    def SetBrightnessLevel(self, sig, value):
        if self.is_valid is False:
            raise CommandGenerateError('Device is invalid!')

        val = self.prs2raw(value)
        cmd = gear.DAPC(self.short_addr, val)
        cmd.sig.set_key(sig.key)
        cmd.sig.set_session_id(sig.session_id)
        if self.is_device:
            if self.is_unaddress_tunned:
                groups = self.get_value(F_GROUPS, [])
                for item in groups:
                    if item['value'] is True:
                        group_id = item['index']
                        self.set_pause_for_group(group_id)
        else:
            if self.tuner:
                self.tuner.set_pause(2+self.fadeTime)
        self.on_command_prepared(cmd)

    def GetBrightnessLevel(self, sig=None):
        _level = self.get_value(STATE_C_LEVEL_RAW, 0)
        _level = self.raw2prs(_level)
        _invalid = STATE_C_LEVEL_RAW in self._invalid_values
        _publish_value = utils.PublishObject(BRIGHTNESS_LEVEL, _level, sig=sig, invalid=_invalid)
        self.publish_value(BRIGHTNESS_LEVEL, _publish_value, retain=True, invalid=_invalid)

    def set_pause_for_group(self, group_id):
        for p_id, _provider in self.manager.providers.items():
            if isinstance(_provider, RapidaDaliDimmer) and _provider.tuner:
                if _provider.is_group and _provider.short_addr.group == group_id:
                    _provider.tuner.set_pause(2+self.fadeTime)

    def serialize(self) -> dict:
        d = super(RapidaDaliLight, self).serialize()
        if d:
            for funit_type in [F_TYPES, F_PHYSICAL_MIN_LEVEL_RAW, F_MIN_LEVEL_RAW, F_MAX_LEVEL_RAW, F_POWER_ON_LEVEL_RAW,
                               F_SYSTEM_FAILURE_LEVEL_RAW, F_FADE_TIME, F_FADE_RATE, F_DIMMING_CURVE, F_SCENE_LEVELS_RAW,
                               F_GROUPS]:
                value = self.get_value(funit_type)
                if value is not None:
                    key = funit_type[0].lower() + funit_type[1:]
                    d[key] = value
        return d


""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
"""                                 DIMMER                                 """
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""


class RapidaDaliDimmer(RapidaDaliLight):
    def __init__(self, data):
        super(RapidaDaliDimmer, self).__init__(data)
        self.step_cmd = None

    def on_command_sended(self, cmd):
        if cmd.is_levels_dependent:
            _p_ids = self.get_members()
            if not self.is_device:
                _p_ids.append(self.id)

            for _p_id in _p_ids:
                _provider = self.manager.providers[_p_id]
                if isinstance(_provider, RapidaDaliLight):
                    value = None
                    if isinstance(cmd, gear.DAPC):
                        value = cmd.frame.pack[1]
                    elif isinstance(cmd, gear.GoToScene):
                        scenes = _provider.get_value(F_SCENE_LEVELS_RAW, None)
                        scene_id = cmd.frame.pack[1] - 0x10
                        if scenes is not None and scene_id in scenes and scenes[scene_id] in range(0, 254):
                            value = scenes[scene_id]

                    if value is not None:
                        if _provider.is_valid:
                            if value > 0:
                                value = max(_provider.get_value(F_MIN_LEVEL_RAW, 0), value)
                                value = min(_provider.get_value(F_MAX_LEVEL_RAW, 254), value)
                            _resp = utils.PublishObject(STATE_C_LEVEL_RAW, value, cmd.sig)
                            _provider.on_update(STATE_C_LEVEL_RAW, _resp, retain=True)
            if self.tuner:
                self.tuner.check_state(cmd)

            self.query_level(cmd.sig)

        super(RapidaDaliDimmer, self).on_command_sended(cmd)

    def SetTuning(self, sig, value, speed=None):
        _c_val = self.get_value(F_TUNING, 0)
        if _c_val * value <= 0:
            speed = 0.1 if speed is None else speed
            if self._tuner is None:
                self._tuner = TunerLimited(self)
            self._generate_def_value(F_TUNING, value)
            if value == 0:
                self._tuner.stop()
            elif value > 0:
                self._tuner.set_direction(gear.StepUp(self.short_addr), speed)
            else:  # value < 0
                self._tuner.set_direction(gear.StepDown(self.short_addr), speed)


""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
"""                              COLOR CONTROL                             """
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""


class RapidaDaliTunableWhite(RapidaDaliDimmer):
    def __init__(self, *args, **kwargs):
        super(RapidaDaliTunableWhite, self).__init__(*args, **kwargs)
        self.temperature_timer = None

    def get_info(self):
        super(RapidaDaliTunableWhite, self).get_info()
        if self.is_device:
            self.GetTemperature()
            self.GetCoolest()
            self.GetWarmest()

    def _get_color_value(self, funit_type, value_type: int, sig=None):
        res = 0xff
        try:
            self.manager.send_interface.send(gear.DTR0(value_type))
            res = self.manager.send_interface.send(cc.QueryColorValue(self.short_addr)).value.as_integer
            if res != 0xff:
                b0 = self.manager.send_interface.send(gear.QueryContentDTR0(self.short_addr)).value.as_integer
                b1 = self.manager.send_interface.send(gear.QueryContentDTR1(self.short_addr)).value.as_integer
                res = int(1000000 / int.from_bytes([b0, b1], 'little'))
        except:
            pass
        finally:
            self._generate_def_value(funit_type, res, invalid=res == 0xff, sig=sig)

    def _set_color_limit(self, value_type: int, value: int):
        if not 1000 <= value <= 20000:
            raise ValueError("temperature must be in the range 1000..20000")
        mirek = int(1000000 / value)
        self._params = [int(b) for b in mirek.to_bytes(2, 'little')] + [value_type]
        self.manager.send_interface.send(cc.StoreColourTemperatureLimit(self.short_addr))

    def SetTemperature(self, sig, temperature=1):
        if not 1000 <= temperature <= 20000:
            raise ValueError("temperature must be in the range 1000..20000")
        try:
            mirek = int(1000000 / temperature)
            bts = [int(b) for b in mirek.to_bytes(2, 'little')]
            self.manager.send_interface.send(gear.DTR0(bts[0]))
            self.manager.send_interface.send(gear.DTR1(bts[1]))
            self.manager.send_interface.send(cc.SetTemperature(self.short_addr))
            self.manager.send_interface.send(cc.Activate(self.short_addr))
        except BaseException as ex:
            logging.error(ex)
        else:
            self.query_temperature()

    def query_temperature(self):
        if self.temperature_timer:
            self.temperature_timer.cancel()
        mc = MultiCommand(F_TEMPERATURE, self.GetTemperature)
        self.temperature_timer = threading.Timer(interval=self.fadeTime, function=self.manager.add_command, args=[self, mc])
        self.temperature_timer.start()

    def GetTemperature(self, sig=None):
        self._get_color_value(F_TEMPERATURE, cc.QueryColorValue.TEMPERATURE, sig=sig)

    def SetCoolest(self, sig=None, value=0):
        try:
            self._set_color_limit(cc.StoreColourTemperatureLimit.COOLEST, value)
        except BaseException as ex:
            logging.error(ex)
        else:
            self.GetCoolest(sig)

    def GetCoolest(self, sig=None):
        self._get_color_value(F_COOLEST, cc.QueryColorValue.COOLEST, sig=sig)

    def SetWarmest(self, sig=None, value=0):
        try:
            self._set_color_limit(cc.StoreColourTemperatureLimit.WARMEST, value)
        except BaseException as ex:
            logging.error(ex)
        else:
            self.GetWarmest(sig)

    def GetWarmest(self, sig=None):
        self._get_color_value(F_WARNEST, cc.QueryColorValue.WARMEST, sig=sig)


""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
"""                                 SWITCH                                 """
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""


class RapidaDaliRelay(RapidaDaliLight):
    pass
