import json
import logging
import struct
import threading

import spread_core.protocols.dali.device.general as device
from spread_core.bam.dali import *
from spread_core.bam.dali import scanner
from spread_core.bam.dali.providers.providers import RapidaDaliProvider
from spread_core.bam.multi_command import MultiCommand
from spread_core.bam.providers import UObj
from spread_core.mqtt import variables
from spread_core.protocols.dali import address
from spread_core.protocols.dali.device import light_sensor_ext, presence_sensor_ext
from spread_core.protocols.dali.exceptions import CommandGenerateError
from spread_core.protocols.dali.gear.events import PresenceEvent, Event

""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
"""                                  DALI 2                                """
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""


class RapidaDaliSensor(RapidaDaliProvider):
    _type_id = None
    _dali_type = 2

    @property
    def instance(self):
        return address.InstanceType(self.type_id)

    @property
    def type_id(self):
        return self._type_id

    def _apply_cmd(self, cmd, *args):
        if issubclass(cmd, device._StandardInstanceCommand):
            return cmd(self.short_addr, self.instance, *args)
        else:
            return cmd(self.short_addr, *args)

    def check_valid(self):
        super(RapidaDaliSensor, self).check_valid()
        if self.is_device:
            cmd = device.QueryInstanceStatus(self.short_addr.address, self.instance)
            status = self._manager.send_interface.send(cmd)
            self.on_update(cmd.funit_type[0], status)

    def on_survey(self):
        super(RapidaDaliSensor, self).on_survey()
        if F_SERIAL_MIN in self.values:
            return

        self._manager.add_survey(self, device.QueryInstanceStatus(self.short_addr.address, self.instance))

    def get_info(self):
        super(RapidaDaliSensor, self).get_info()
        self._generate_def_value(F_INSTANCES_TYPE, self.instance._value)
        self.request(device.QueryNumberOfInstances(self.short_addr))
        if F_INSTANCES_INDEX not in self.values:
            self.GetInstanceIndex()
        self.request(device.QueryInstanceEnabled(self.short_addr, self.instance))
        self.request(device.QueryEventScheme(self.short_addr, self.instance))
        self.request(device.QueryResolution(self.short_addr, self.instance))
        if self.get_value(F_ON, False):
            self.get_event_value()
        self._manager.add_info(self, device.QueryEventPriority(self.short_addr, self.instance))
        self._manager.add_info(self, device.QueryEventFilterL(self.short_addr, self.instance))
        self._manager.add_info(self, device.QueryOperatingMode(self.short_addr))
        self._manager.add_info(self, device.QueryPrimaryInstanceGroup(self.short_addr, self.instance))
        self._manager.add_info(self, device.QueryInstanceGroup1(self.short_addr, self.instance))
        self._manager.add_info(self, device.QueryInstanceGroup2(self.short_addr, self.instance))
        self._manager.add_info(self, MultiCommand(F_FEATURE_TYPES, self.fill_feature_types))

    def get_event_value(self):
        resolution = self.get_value(F_RESOLUTION)
        if resolution is not None:
            r = self._manager.send_interface.send(device.QueryInputValue(self.short_addr, self.instance))
            if r is not None and r.value is not None:
                _val = bin(r.value.as_integer)[2:].rjust(8, '0')
                while True:
                    r = self._manager.send_interface.send(device.QueryInputValueLatch(self.short_addr, self.instance))
                    if r is None or r._value is None:
                        break
                    _val += bin(r.value.as_integer)[2:].rjust(8, '0')

                _val = _val.ljust(resolution, '0')[:resolution]
                _val = int(_val[:10], 2)
                event = Event.of(_val.to_bytes(3, 'big'))
                self.on_event(event)

    def fill_feature_types(self):
        resp = self._manager.send_interface.send(device.QueryFeatureType(self.short_addr, self.instance))
        _arr = []
        if resp and resp.value:
            if resp.value.as_integer == 0xff:
                _r = None
                while _r is None or _r.value.as_integer == 0xfe or _r.value.as_integer == 0xff:
                    _r = self.request(device.QueryNextFeatureType(self.short_addr, self.instance))
                    if _r is None or _r.value is None or _r.value.as_integer == 0xfe:
                        break
                    _arr.append(_r.value.as_integer)
            elif resp.value.as_integer != 0xfe:
                _arr = [resp.value.as_integer]

        self._generate_def_value(F_FEATURE_TYPES, _arr)

    def on_update(self, funit_type, response, retain=True, invalid=False):
        invalid = invalid or response.value is None or (hasattr(response.value, 'error') and response.value.error)
        super(RapidaDaliSensor, self).on_update(funit_type, response, retain, invalid)
        funit = self.get_funit(funit_type)
        if funit and variables.GET in funit and 'cmd' in funit[variables.GET] and issubclass(funit[variables.GET]['cmd'], device._StandardDeviceCommand):
            for _id in self._manager._addresses[self.short_addr.address]:
                if isinstance(self._manager._providers[_id], RapidaDaliSensor):
                    if self.id !=_id:
                        self._manager._providers[_id].publish_value(funit_type, response, retain, invalid)

    def on_event(self, event):
        raise NotImplementedError()

    def read_memory_location(self, bank_id, start_address, end_address):
        return scanner.Bus2.read_memory_location(self._manager.send_interface, self.short_addr.address, bank_id, start_address, end_address)

    def set_dtr_command(self, index, val):
        if index == 0:
            return device.DTR0(val)
        elif index == 1:
            return device.DTR1(val)
        elif index == 2:
            return device.DTR2(val)
        else:
            raise CommandGenerateError('комманды DTR{} не уществует'.format(index))

    def SetShortAddress(self, sig, new_addr):
        _dtr0 = None
        _provider = None
        new_short = None
        if new_addr != self.short_addr.address:
            if self.is_device:
                old_short = self.short_addr
                if new_addr is not None:
                    new_short = address.Short(new_addr)
                    res = self.send(device.QueryNumberOfInstances(new_short))
                    if res.value is not None and res.value.as_integer > 0:
                        for p_id in self._manager._addresses[new_addr].copy():
                            _provider = self._manager._providers[p_id]
                            if isinstance(_provider, self.__class__):
                                old_long = []
                                new_long = []

                                self.send(device.Terminate())

                                self.send(device.Initialise(old_short.address))
                                self.send(device.Initialise(new_short.address))

                                old_long.append(self.send(device.QueryRandomAddressH(old_short)))
                                old_long.append(self.send(device.QueryRandomAddressM(old_short)))
                                old_long.append(self.send(device.QueryRandomAddressL(old_short)))

                                new_long.append(self.send(device.QueryRandomAddressH(new_short)))
                                new_long.append(self.send(device.QueryRandomAddressM(new_short)))
                                new_long.append(self.send(device.QueryRandomAddressL(new_short)))

                                self.send(device.SearchAddrH(old_long[0].value.as_integer))
                                self.send(device.SearchAddrM(old_long[1].value.as_integer))
                                self.send(device.SearchAddrL(old_long[2].value.as_integer))
                                self.send(device.ProgramShortAddress(new_short.address))

                                self.send(device.SearchAddrH(new_long[0].value.as_integer))
                                self.send(device.SearchAddrM(new_long[1].value.as_integer))
                                self.send(device.SearchAddrL(new_long[2].value.as_integer))
                                self.send(device.ProgramShortAddress(old_short.address))

                                self.send(device.Terminate())

                                break
                            else:
                                _provider = None
                        else:

                            raise CommandGenerateError('Address({}) is not free'.format(new_addr))
                    else:
                        _dtr0 = device.DTR0(new_addr)
                    # _dtr0 = device.DTR0(new_addr)

                    if new_addr not in self._manager._addresses:
                        self._manager._addresses[new_addr] = []
                else:
                    _dtr0 = device.DTR0(0xff)

                if _dtr0 is not None:
                    self.send(_dtr0)
                    self.send(device.SetShortAddress(old_short))

                _providers = []

                if _provider:
                    for addr in [old_short, new_short]:
                        for p_id in self._manager._addresses[addr.address].copy():
                            _provider = self._manager._providers[p_id]
                            if isinstance(_provider, RapidaDaliSensor):
                                _provider.set_valid(False)
                                _providers.append(_provider)
                                # _provider.SetBindingDevice(sig, (old_short if addr == new_short else new_short).address)

                    for _provider in _providers:
                        _provider.values[F_BINDING_DEVICE] = None
                        _provider.SetBindingDevice(sig, _provider.short_addr.address)
                        _provider.get_info()
                else:
                    for addr in [old_short, new_short]:
                        for p_id in self._manager._addresses[addr.address].copy():
                            _provider = self._manager._providers[p_id]
                            if isinstance(_provider, RapidaDaliSensor):
                                _provider.set_valid(False)
                                _provider.check_valid()
                                # _provider.publish_all(sig)
            else:
                raise CommandGenerateError('You can not give an address to {}'.format(self.binding.b_type))

    def SetEnable(self, sig, value):
        if self.get_value('On') != value:
            if value is True:
                self.send(device.EnableInstance(self.short_addr, self.instance))
            else:
                self.send(device.DisableInstance(self.short_addr, self.instance))

            if self.is_device:
                _p_ids = [self.id]
            elif self.is_group:
                _p_ids = self.get_group_members()
            else:
                _p_ids = self.get_broadcast_members()
            for _p_id in _p_ids:
                _provider = self._manager._providers[_p_id]
                if isinstance(_provider, RapidaDaliSensor) and _provider.is_device:
                    cmd = device.QueryInstanceEnabled(self.short_addr, self.instance)
                    cmd.sig.set_session_id(sig.session_id)
                    cmd.sig.set_key(sig.key)
                    self.request(cmd)

    def SetDiscovery(self, sig, value):
        _discovery = self.get_value(F_DISCOVERY, False)
        if _discovery != value:
            self.set_value(F_DISCOVERY, value)
            self._generate_def_value(F_DISCOVERY, value, sig=sig)

            if _discovery is False and value is True:
                self.check_discovery()
            else:
                self.send(device.Terminate())

    def check_discovery(self):
        if self.get_value(F_DISCOVERY) is True:
            self.send(device.IdentifyDevice(self.short_addr))
            threading.Timer(7, function=self.check_discovery).start()

    def GetGroups(self, sig=None):
        self.check_command_for_device()
        _groups = []

        resp_0_7 = self.send(device.QueryDeviceGroupsZeroToSeven(self.short_addr))
        if resp_0_7 and resp_0_7.value is not None and not resp_0_7.value.error:
            for _i in range(0, 8):
                _include = resp_0_7.value.as_integer & (1 << _i) == (1 << _i)
                _groups.append(dict(index=_i, value=_include))
                if _include:
                    self._manager.add_to_group(2, _i, self.id)

        resp_8_15 = self.send(device.QueryDeviceGroupsEightToFifteen(self.short_addr))
        if resp_8_15 and resp_8_15.value is not None and not resp_8_15.value.error:
            for _i in range(0, 8):
                _include = resp_8_15.value.as_integer & (1 << _i) == (1 << _i)
                _groups.append(dict(index=(8+_i), value=_include))
                if _include:
                    self._manager.add_to_group(2, 8+_i, self.id)

        resp_16_23 = self.send(device.QueryDeviceGroupsSixteenToTwentyThree(self.short_addr))
        if resp_16_23 and resp_16_23.value is not None and not resp_16_23.value.error:
            for _i in range(0, 8):
                _include = resp_16_23.value.as_integer & (1 << _i) == (1 << _i)
                _groups.append(dict(index=(16+_i), value=_include))
                if _include:
                    self._manager.add_to_group(2, 16+_i, self.id)

        resp_24_31 = self.send(device.QueryDeviceGroupsTwentyFourToThirtyOne(self.short_addr))
        if resp_24_31 and resp_24_31.value is not None and not resp_24_31.value.error:
            for _i in range(0, 8):
                _include = resp_24_31.value.as_integer & (1 << _i) == (1 << _i)
                _groups.append(dict(index=(24+_i), value=_include))
                if _include:
                    self._manager.add_to_group(2, 24+_i, self.id)

        self._generate_def_value(F_GROUPS, _groups, sig=sig)

    def SetGroups(self, sig, val):
        self.check_command_for_device()
        if not isinstance(val, list):
            val = json.loads(val)
        _val = dict()
        for item in val:
            _val[item['index']] = item['value']

        c_val = self.get_value(F_GROUPS, dict())
        _c_val = dict()
        for item in c_val:
            _c_val[item['index']] = item['value']

        for r_i in range(0, 2):
            _dtr_a = 0x0
            _dtr_r = 0x0
            for _i, _inc in _val.items():
                if _i not in range(r_i*16, r_i*16+16):
                    continue
                if _inc is True:
                    if _i not in _c_val or _c_val[_i] != _val[_i]:
                        _dtr_a += 1 << (_i % 16)
                        self._manager.add_to_group(2, _i, self.id)
                elif _i in _c_val and _c_val[_i] is True:
                    _dtr_r += 1 << (_i % 16)
                    self._manager.remove_from_group(2, _i, self.id)

                _c_val[_i] = _inc

            if _dtr_a > 0:
                _dtr1, _dtr2 = struct.pack('<H', int(_dtr_a))
                self.send(device.DTR2DTR1(_dtr2, _dtr1))
                if r_i == 0:
                    self.send(device.AddToDeviceGroupsZeroToFifteen(self.short_addr))
                else:
                    self.send(device.AddToDeviceGroupsSixteenToThirtyOne(self.short_addr))

            if _dtr_r > 0:
                _dtr1, _dtr2 = struct.pack('<H', _dtr_r)
                self.send(device.DTR2DTR1(_dtr2, _dtr1))
                if r_i == 0:
                    self.send(device.RemoveFromDeviceGroupsZeroToFifteen(self.short_addr))
                else:
                    self.send(device.RemoveFromDeviceGroupsSixteenToThirtyOne(self.short_addr))

        res = []
        for _i, _inc in _c_val.items():
            res.append({'index': _i, 'value': _inc})

        self._generate_def_value(F_GROUPS, res, sig=sig)

    def GetFeatureTypes(self, sig):
        self.check_command_for_device()
        self._generate_def_value(F_FEATURE_TYPES, self.get_value(F_FEATURE_TYPES, []), sig=sig)

    def GetInstanceIndex(self, sig=None):
        self.check_command_for_device()
        val = 0
        invalid = True
        if F_INSTANCES_NUMBER in self.values:
            for instance_num in range(0, self.values[F_INSTANCES_NUMBER]):
                tp = self._manager.send_interface.send(
                    device.QueryInstanceType(self.short_addr, address.InstanceNumber(instance_num)))
                if tp and tp.value:
                    if tp.value.as_integer == self.instance._value:
                        val = instance_num
                        invalid = False
                        break

        self._generate_def_value(F_INSTANCES_INDEX, self.get_value(F_INSTANCES_INDEX, val), sig=sig, invalid=invalid)

    def serialize(self) -> dict:
        d = super(RapidaDaliSensor, self).serialize()
        if d:
            for funit_type in [F_OPERATIONG_MODE, F_GROUPS, F_INSTANCES_NUMBER]:
                value = self.get_value(funit_type)
                if value is not None:
                    key = funit_type[0].lower() + funit_type[1:]
                    d[key] = value
        return d

    def serialize_instance(self) -> dict:
        i = {}
        value = self.get_value(F_INSTANCES_INDEX)
        if value is None: return {}
        else: i['index'] = value

        value = self.get_value(F_INSTANCES_TYPE)
        if value: i['type'] = value

        value = self.get_value(F_ON)
        if value is not None: i['enabled'] = value

        for funit_type in [F_GROUP0, F_GROUP1, F_GROUP2, F_RESOLUTION, F_EVENT_SCHEME, F_EVENT_PRIORITY, F_FEATURE_TYPES,
                           F_EVENT_FILTER, F_DEAD_TIME, F_HOLD_TIME, F_REPORT_TIME]:
            value = self.get_value(funit_type)
            if value is not None:
                key = funit_type[0].lower() + funit_type[1:]
                i[key] = value
        return i


""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
"""                               Light Sensor                             """
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""


class RapidaDaliLightSensor(RapidaDaliSensor):
    _type_id = 4

    def on_event(self, event):
        # if F_ON in self.values and self.values[F_ON] is False:
        #     return
        logging.debug(f'LIGHT EVENT: {event}')
        self.on_update(STATE_C_LUMINOSITY, UObj(STATE_C_LUMINOSITY, event.value), retain=True)

    def get_info(self):
        if self.is_device:
            super(RapidaDaliLightSensor, self).get_info()
            self._manager.add_info(self, light_sensor_ext.QueryDeadTime(self.short_addr, self.instance))
            self._manager.add_info(self, light_sensor_ext.QueryReportTime(self.short_addr, self.instance))
            self._manager.add_info(self, light_sensor_ext.QueryHysteresis(self.short_addr, self.instance))
            self._manager.add_info(self, light_sensor_ext.QueryHysteresisMin(self.short_addr, self.instance))

    def GetCurrentLuminosity(self, sig):
        self.check_command_for_device()
        val = self.get_value(STATE_C_LUMINOSITY, 0)
        self._generate_def_value(STATE_C_LUMINOSITY, val, invalid=val is None, sig=sig)

    def serialize_instance(self) -> dict:
        d = super(RapidaDaliLightSensor, self).serialize_instance()
        for funit_type in [F_HYSTERESIS, F_PHYSICAL_MIN_LEVEL_RAW]:
            value = self.get_value(funit_type)
            if value is not None:
                key = funit_type[0].lower() + funit_type[1:]
                d[key] = value
        return d


""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
"""                             Presence Sensor                            """
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""


class RapidaDaliPresenceSensor(RapidaDaliSensor):
    _type_id = 3

    def on_event(self, event):
        # if F_ON in self.values and self.values[F_ON] is False:
        #     return
        presence = PresenceEvent(event.value)
        logging.debug(f'PRESENCE EVENT: {event} {presence.value}')
        self.on_update(STATE_C_PRESENCE, UObj(STATE_C_PRESENCE, presence.value), retain=True)

    def get_info(self):
        super(RapidaDaliPresenceSensor, self).get_info()
        self._manager.add_info(self, presence_sensor_ext.QueryDeadTime(self.short_addr, self.instance))
        self._manager.add_info(self, presence_sensor_ext.QueryReportTime(self.short_addr, self.instance))
        self._manager.add_info(self, presence_sensor_ext.QueryHoldTime(self.short_addr, self.instance))

    def GetCurrentPresence(self, sig):
        self.check_command_for_device()
        val = self.get_value(STATE_C_PRESENCE)
        self._generate_def_value(STATE_C_PRESENCE, self.get_value(STATE_C_PRESENCE, 0), invalid=val is None, sig=sig)
