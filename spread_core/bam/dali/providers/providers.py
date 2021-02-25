import threading

from spread_core import mqtt
from spread_core.bam.dali import *
from spread_core.bam.dali import bindings
from spread_core.bam.multi_command import MultiCommand
from spread_core.bam.providers import Provider
from spread_core.errors.project_errors import JocketError
from spread_core.mqtt.variables import VariableJocket, SET, GET
from spread_core.protocols.dali.command import YesNoResponse, CommandSignature
from spread_core.protocols.dali.exceptions import CommandGenerateError
from spread_core.tools import settings, utils
from spread_core.tools.settings import logging


# говно-версия
# RETAINED = [F_BINDING, F_BINDING_DEVICE, F_BINDING_GROUP, F_DIMMING_CURVE, STATE_C_LEVEL_RAW, F_DISCOVERY]
# говно-версия END


class RapidaDaliProvider(Provider):
    _dali_type = 0

    def __init__(self, data):
        super(RapidaDaliProvider, self).__init__(data)
        self.valid_timer = None

        f_unit = bindings.BINDING
        _exist, _ower = settings.get_dump(data['type'], data['id'], f_unit)
        data['attributes']['def_' + f_unit.lower()] = data['attributes'][f_unit.lower()]
        if _exist:
            data['attributes'][f_unit] = _ower

        f_unit = bindings.BINDING + bindings.DEVICE
        data['attributes']['def_' + bindings.DEVICE.lower()] = data['attributes'][bindings.DEVICE.lower()]
        _exist, _ower = settings.get_dump(data['type'], data['id'], f_unit)
        if _exist:
            data['attributes'][bindings.DEVICE.lower()] = _ower

        f_unit = bindings.BINDING + bindings.GROUP
        data['attributes']['def_' + bindings.GROUP.lower()] = data['attributes'][bindings.GROUP.lower()]
        _exist, _ower = settings.get_dump(data['type'], data['id'], f_unit)
        if _exist:
            data['attributes'][bindings.GROUP.lower()] = _ower

        self._binding = bindings.of(data['attributes'])

    def __str__(self):
        return ('!!!INVALID!!!' if self._valid is False else '') + 'id: {}; binding: {}'.format(self.id, self.binding)

    @property
    def surveyable(self):
        if self.is_device:
            return super(RapidaDaliProvider, self).surveyable

        return False

    @property
    def binding(self):
        return self._binding

    @property
    def short_addr(self):
        return self.binding.addr

    @property
    def is_device(self):
        return isinstance(self.binding, bindings.BindingDevice)

    @property
    def is_group(self):
        return isinstance(self.binding, bindings.BindingGroup)

    @property
    def is_broadcast(self):
        return isinstance(self.binding, bindings.BindingBroadcast)

    @property
    def is_unaddressed(self):
        return isinstance(self.binding, bindings.BroadcastUnaddressed)

    def get_group_members(self):
        if self.is_group:
            if self._dali_type > 0:
                return self._manager.get_group_members(self._dali_type, self.short_addr.group)
        return []

    def get_broadcast_members(self):
        if self.is_broadcast:
            if self._dali_type > 0:
                return self._manager.get_all_devices(self._dali_type)
        return []

    def get_members(self) -> []:
        if self.is_group:
            return self.get_group_members()
        elif self.is_broadcast:
            return self.get_broadcast_members()

        return [self.id]

    def transform_value(self, funit_type, response, invalid):
        if isinstance(response, YesNoResponse):
            val = response.value
        elif isinstance(response.value, dict):
            val = response.value[funit_type]
        elif hasattr(response.value, 'as_integer'):
            val = response.value.as_integer
        else:
            val = response.value

        if invalid:
            _val = self.get_value(funit_type, val)
            if _val is not None:
                val = _val
        else:
            funit = self.get_funit(funit_type)
            if funit:
                if mqtt.VARIANTS in funit:
                    if val is not None:
                        if val in funit[mqtt.VARIANTS]:
                            index = funit[mqtt.VARIANTS].index(val)
                        else:
                            index = val
                        try:
                            val = funit[mqtt.VARIANTS][index]
                        except BaseException as ex:
                            print(str(ex))
                    else:
                        val = funit[mqtt.variables.STATE]()
                elif mqtt.MASK in funit:
                    if val is not None:
                        if isinstance(val, int):
                            index = val
                            arr = funit[mqtt.MASK]
                            val = []
                            for ind in range(0, len(arr)):
                                if index & (1 << ind):
                                    val.append(arr[ind])
                    else:
                        val = funit[mqtt.variables.STATE]()
                elif funit_type == F_TYPES:
                    if isinstance(val, int):
                        val = [val]

        return val

    def publish_value(self, funit_type, response, retain=True, invalid=False):
        val = self.transform_value(funit_type, response, invalid)

        funit = self.get_funit(funit_type)
        if funit:
            class_id = funit['id']
            jocket = VariableJocket.create_data(id=self.id, cl=class_id, action='state', val=val, invalid=invalid)
            if hasattr(response, '_sig') and response.sig and response.sig.key:
                jocket.key = response.sig.key

            # говно-версия
            # if not self._manager.use_retain \
            #         or funit_type not in self.values \
            #         or self.values[funit_type] != val \
            #         or invalid is True \
            #         or funit_type in self._invalid_values:
            #     state_topic = mqtt.TopicState(self._manager.project_id, self.get_address(funit_type))
            #     if funit_type in RETAINED or not self.is_device:
            #         self._manager.publish_retain(state_topic, jocket.pack(), retain)
            #     else:
            #         self._manager.publish(state_topic, jocket.pack(), retain)
            #
            #     self.set_value(funit_type, val)
            #     if invalid:
            #         self._invalid_values.append(funit_type)
            #     elif funit_type in self._invalid_values:
            #         self._invalid_values.remove(funit_type)

            if funit_type not in self.values or self.values[funit_type] != val or invalid is True or funit_type in self._invalid_values:
                state_topic = mqtt.TopicState(self._manager.project_id, self.get_address(funit_type))
                self._manager.publish(state_topic, jocket.pack(), retain)
                self.set_value(funit_type, val)
                if invalid:
                    self._invalid_values.append(funit_type)
                elif funit_type in self._invalid_values:
                    self._invalid_values.remove(funit_type)
            # говно-версия END

            if hasattr(response, '_sig') and response.sig and response.sig.session_id:
                reply_topic = mqtt.TopicReply(self._manager.project_id, response.sig.session_id)
                self._manager.publish(reply_topic, jocket.pack(), retain=False)

    def on_state(self, funit_type, value):
        self.values[funit_type] = value

        if funit_type == F_GROUPS and self.is_device:
            for item in value:
                if item['value'] is True:
                    self.manager.add_to_group(self._dali_type, item['index'], self.id)

    def on_request_answer(self, funit_type, response):
        if isinstance(response, YesNoResponse) or response._value is not None:
            super(RapidaDaliProvider, self).on_request_answer(funit_type, response)

    def on_update(self, funit_type, response, retain=True, invalid=False):
        self.publish_value(funit_type, response, retain, invalid)
        if funit_type == F_VALIDATOR:
            self.stop_invalid_timer()
            if self.is_valid and response.error:
                self.set_valid(False)
            elif not self.is_valid and not response.error:
                self.set_valid(True)
            # elif not self.is_valid and not response.error:
            #     try:
            #         _serial_min = ''.join(hex(b)[2:].rjust(2, '0') for b in self.read_memory_location(0, 0x11, 0x13)).upper()
            #     except BaseException as ex:
            #         logging.warning('Fail SerialMin Query!')
            #     else:
            #         if _serial_min:
            #             _serial = self.get_value('Serial', 'xyu')
            #             if _serial_min in _serial and _serial.index(_serial_min) == len(_serial) - 4:
            #                 self.set_valid(True)
            #             else:
            #                 logging.warning('SerialMin({}) is not equal Serial({})!'.format(_serial_min, _serial))
            #                 self._generate_def_value(F_SERIAL_MIN', _serial_min)

    def on_command(self, topic, jocket):
        cmds = {self: []}
        act = jocket.action
        funit = topic.entity_addr.funit
        funit_type = topic.entity_addr.funit_type
        args = []
        if act in funit:
            if 'cmd' in funit[act]:
                cmd = funit[act]['cmd']
                if act == SET:
                    val = jocket.value
                    if mqtt.VARIANTS in funit:
                        if val in funit[mqtt.VARIANTS]:
                            val = funit[mqtt.VARIANTS].index(val)
                        else:
                            raise JocketError('<<{}>> is not included in the list of permissible values of the classifier {}!'.format(val, funit[
                                mqtt.VARIANTS]))
                    elif mqtt.MASK in funit:
                        _val = 0
                        for _item in val:
                            _val += (1 << funit[mqtt.MASK].index(_item))
                        val = _val

                    if cmd._uses_dtr1:
                        cmds[self].append(self.set_dtr_command(1, 0))
                        print('NEED DTR1!')

                    if cmd._uses_dtr2:
                        cmds[self].append(self.set_dtr_command(2, 0))
                        print('NEED DTR2!')

                    if cmd._uses_dtr0:
                        cmds[self].append(self.set_dtr_command(0, val))
                    else:
                        args.append(val)

                    cmd = self._apply_cmd(cmd, *args)
                    cmd.sig.set_key(jocket.key)
                    cmds[self].append(cmd)
                else:
                    if not self.is_device:
                        self._generate_def_value(funit_type, self.get_value(funit_type, None),
                                                 funit_type not in self.values,
                                                 sig=CommandSignature(jocket.key, topic.session_id))
                        # raise JocketError('The {} command cannot be applied to an object that is not an DEVICE!'.format(act))

            elif 'func' in funit[act]:
                if funit[act]['func'] in dir(self):
                    if mqtt.variables.DATA in jocket.data:
                        params = jocket.data[mqtt.variables.DATA]
                        params.pop(mqtt.variables.VALUE)
                    else:
                        params = dict()
                    cmd = MultiCommand(topic.entity_addr.funit_type, getattr(self, funit[act]['func']), jocket.value, **params)
                    cmd.set_signature(jocket.key, topic.session_id)
                    cmds[self].append(cmd)
                else:
                    raise JocketError(
                        '<<{}>>  of <<{}>> is not implemented in <<{}>>!'.format(funit[act]['func'],
                                                                                 topic.entity_addr.funit_type,
                                                                                 self.__class__.__name__))

            elif 'value' in funit[act]:
                _value = None
                if funit_type in self.values:
                    _value = self.get_value(funit_type)
                    _invalid = False
                else:
                    _invalid = True

                self._generate_def_value(funit_type, _value, _invalid, sig=CommandSignature(jocket.key, topic.session_id))
            else:
                raise JocketError(
                    '<<{}>> is not implemented in classifier for <<{}>>!'.format(act, self.__class__.__name__))

            if ((act == SET and GET in funit and 'func' not in funit[SET]) or act == GET) and 'cmd' in funit[GET]:
                if self.is_device:
                    _p_ids = [self.id]
                else:
                    if funit_type != STATE_C_LEVEL_RAW:
                        sig = CommandSignature(jocket.key, topic.session_id)
                        if not self.is_device:
                            if act == SET:
                                _value = jocket.value
                            else:
                                _value = self.get_value(funit_type)
                        else:
                            _value = jocket.value
                        _resp = utils.PublishObject(funit_type, _value, sig)
                        self.on_update(funit_type, _resp, retain=True, invalid=jocket.invalid)

                    _p_ids = self.get_members()

                if self.is_device or act == SET:
                    if funit_type != STATE_C_LEVEL_RAW:
                        try:
                            for _p_id in _p_ids:
                                _provider = self._manager._providers[_p_id]
                                if _provider.is_device:
                                    cmd = _provider._apply_cmd(funit[GET]['cmd'], *args)
                                    cmd.sig.set_key(jocket.key)
                                    cmd.sig.set_session_id(topic.session_id)
                                    if _provider not in cmds:
                                        cmds[_provider] = []
                                    cmds[_provider].append(cmd)
                        except BaseException as ex:
                            logging.exception(ex)
        else:
            raise JocketError('<<{}>>  of <<{}>> is not present in <<{}>>!'.format(act, topic.entity_addr.funit_type, self.__class__.__name__))

        if len(cmds) > 0:
            for _provider, _cmds in cmds.items():
                _provider.on_command_prepared(*_cmds)

    def set_dtr_command(self, index, val):
        raise NotImplementedError()

    def _apply_cmd(self, cmd, *args):
        raise NotImplementedError()

    def on_exit(self):
        for funit_type in self.values:
            topic = mqtt.TopicState(self._manager.project_id, self.get_address(funit_type))
            funit = mqtt.classifier[self._manager.__class__.__name__][self.__class__.__name__]
            class_id = funit[funit_type]['id']
            jocket = VariableJocket.create_data(id=self.id, cl=class_id, action='state', val=self.values[funit_type], invalid=True)
            self._manager.publish(topic, jocket.pack(), True)

    def get_bindings(self):
        self.GetBinding()
        self.GetBindingDevice()
        self.GetBindingGroup()

    def get_info(self):
        if F_SERIAL_MIN in self.values:
            _serial = self.get_value(F_SERIAL, 'xyu')
            _serial_min = self.get_value(F_SERIAL_MIN, 'xyuMin')
            if _serial_min not in _serial or _serial.index(_serial_min) != len(_serial) - 4:
                for funit_type in self.values:
                    if funit_type not in [F_BINDING, F_BINDING_DEVICE, F_BINDING_GROUP]:
                        self.values.pop(funit_type)
        if F_SERIAL not in self.values:
            self._manager.add_info(self, MultiCommand(F_SERIAL, self.Serial))
        if F_GTIN not in self.values:
            self._manager.add_info(self, MultiCommand(F_GTIN, self.Gtin))
        if F_FIRMWARE not in self.values:
            self._manager.add_info(self, MultiCommand(F_FIRMWARE, self.FirmwareVersion))
        if F_HARDWARE not in self.values:
            self._manager.add_info(self, MultiCommand(F_HARDWARE, self.HardwareVersion))
        if F_GTIN_OEM not in self.values:
            self._manager.add_info(self, MultiCommand(F_GTIN_OEM, self.GtinOem))
        if F_SERIAL_OEM not in self.values:
            self._manager.add_info(self, MultiCommand(F_SERIAL_OEM, self.SerialOem))
        if F_DISCOVERY not in self.values:
            self._manager.add_info(self, MultiCommand(F_DISCOVERY, self.GetDiscovery))
        if F_GROUPS not in self.values:
            self.GetGroups()

    def on_survey(self):
        pass

    def check_valid(self):
        super(RapidaDaliProvider, self).check_valid()

    def request(self, cmd):
        if F_VALIDATOR in cmd._funit_type:
            if self.is_valid:
                self.start_invalid_timer()
        super(RapidaDaliProvider, self).request(cmd)

    def start_invalid_timer(self):
        self.valid_timer = threading.Timer(1, function=self.set_valid, args=[False])
        self.valid_timer.setName('Valid Timer')
        self.valid_timer.start()

    def stop_invalid_timer(self):
        if self.valid_timer:
            self.valid_timer.cancel()
            self.valid_timer = None

    def set_valid(self, validity):
        super(RapidaDaliProvider, self).set_valid(validity)
        for funit_type in self.values.copy():
            if funit_type not in [F_BINDING, F_BINDING_DEVICE, F_BINDING_GROUP]:
                self._generate_def_value(funit_type, self.get_value(funit_type), invalid=not validity)
                if funit_type in [STATE_C_PRESENCE, STATE_C_LUMINOSITY]:
                    self.values.pop(funit_type)

        # ToDo set INFO QUERIES ro survey
        if validity is True:
            self.on_command_prepared(MultiCommand(None, self.get_info))

    def check_command_for_device(self):
        if not self.is_device:
            raise JocketError('The GET command cannot be applied to an object that is not an DEVICE!')

    def read_memory_location(self, bank_id, start_address, end_address):
        raise NotImplementedError()

    def SetShortAddress(self, sig, new_addr):
        raise NotImplementedError()

    def GetTypes(self, sig=None):
        self._generate_def_value(F_TYPES, self.get_value(F_TYPES, []), sig=sig)

    def GetDiscovery(self, sig=None):
        self._generate_def_value(F_DISCOVERY, self.get_value(F_DISCOVERY, False), sig=sig)

    def SetDiscovery(self, sig, value):
        raise NotImplementedError()

    def GetBinding(self, sig=None):
        self._generate_def_value(F_BINDING, self.binding.b_type, sig=sig)

    def SetBinding(self, sig, value):
        if value not in bindings.ALL:
            raise CommandGenerateError('Binding({}) is not present in available values({})'.format(value, bindings.ALL))

        _c_binding = self.get_value(bindings.BINDING, bindings.DEVICE)
        if _c_binding != value:
            self._binding = bindings.of({
                bindings.BINDING.lower(): value,
                value.lower(): self.get_value((F_BINDING + value), -1),
                'def_' + bindings.BINDING.lower(): self.binding.def_binding
            })

            self._generate_def_value(F_BINDING, value, sig=sig)

    def ResetBinding(self, sig):
        settings.set_dump(self, F_BINDING, settings.KILL_ITEM)
        self.SetBinding(sig, self.binding.def_binding)

    def ResetBindingDevice(self, sig):
        self.SetBindingDevice(sig, self.binding.def_device)
        settings.set_dump(self, F_BINDING_DEVICE, settings.KILL_ITEM)

    def ResetBindingGroup(self, sig):
        self.SetBindingDevice(sig, self.binding.def_group)
        settings.set_dump(self, F_BINDING_GROUP, settings.KILL_ITEM)

    def GetBindingDevice(self, sig=None):
        if self.get_value(bindings.BINDING) == bindings.DEVICE:
            self._generate_def_value(F_BINDING_DEVICE, self.binding.addr.address, sig=sig)
        else:
            self._generate_def_value(F_BINDING_DEVICE, None, sig=sig, invalid=True)

    def SetBindingDevice(self, sig, value):
        if value is None:
            self.set_valid(False)
        elif not isinstance(value, int) and not str.isdigit(str(value)):
            raise CommandGenerateError('Value({}) must be integer!'.format(value))
        else:
            value = int(value)

            if self.get_value(F_BINDING_DEVICE) != value:
                settings.set_dump(self, F_BINDING_DEVICE, value)
                if self.get_value(bindings.BINDING) == bindings.DEVICE:
                    if self.binding.addr.address in self._manager._addresses and self.id in self._manager._addresses[self.short_addr.address]:
                        self._manager._addresses[self.short_addr.address].remove(self.id)
                    self.binding.set_addr(value)
                    if value not in self._manager._addresses:
                        self._manager._addresses[value] = []
                    self._manager._addresses[value].append(self.id)
                    self.check_valid()
                    # self.get_info()
                self._generate_def_value(F_BINDING_DEVICE, value, sig=sig)

    def GetBindingGroup(self, sig=None):
        if self.get_value(bindings.BINDING) == bindings.GROUP:
            self._generate_def_value(F_BINDING_GROUP, self.binding.addr.group, sig=sig)
        else:
            self._generate_def_value(F_BINDING_GROUP, None, sig=sig, invalid=True)

    def SetBindingGroup(self, sig, value):
        if not isinstance(value, int) and not str.isdigit(str(value)):
            raise CommandGenerateError('Value({}) must be integer!'.format(value))

        value = int(value)

        if self.get_value(F_BINDING_GROUP) != value:
            settings.set_dump(self, F_BINDING_GROUP, value)
            if self.get_value(bindings.BINDING) == bindings.GROUP:
                self.binding.set_addr(value)
            self._generate_def_value(F_BINDING_GROUP, value, sig=sig)

    def GetGroups(self, sig=None):
        raise NotImplementedError()

    def SetGroups(self, sig, val):
        raise NotImplementedError()

    def Gtin(self, sig=None):
        self.check_command_for_device()
        _gtin = ''
        _invalid = False
        try:
            _gtin = ''.join(hex(b)[2:].rjust(2, '0') for b in self.read_memory_location(0, 0x3, 0x9)).upper()
        except BaseException as ex:
            logging.error('Error on Gtin: \n {}'.format(ex))
            _invalid = True
        finally:
            for _p_id in self._manager._addresses[self.short_addr.address]:
                if _p_id in self._manager._providers:
                    _provider = self._manager._providers[_p_id]
                    if _provider._dali_type == self._dali_type:
                        _provider._generate_def_value('Gtin', _gtin, invalid=_invalid, sig=sig)

    def FirmwareVersion(self, sig=None):
        self.check_command_for_device()
        _firmware = ''
        _invalid = False
        try:
            _firmware = '.'.join(str(b) for b in self.read_memory_location(0, 0x9, 0xb))
        except BaseException as ex:
            logging.error('Error on FirmwareVersion: \n {}'.format(ex))
            _invalid = True
        finally:
            for _p_id in self._manager._addresses[self.short_addr.address]:
                if _p_id in self._manager._providers:
                    _provider = self._manager._providers[_p_id]
                    if _provider._dali_type == self._dali_type:
                        _provider._generate_def_value('FirmwareVersion', _firmware, invalid=_invalid, sig=sig)

    def Serial(self, sig=None):
        self.check_command_for_device()
        _serial = ''
        _invalid = False
        try:
            _serial = ''.join(hex(b)[2:].rjust(2, '0') for b in self.read_memory_location(0, 0xb, 0x13)).upper()
        except BaseException as ex:
            logging.error('Error on Serial: \n {}'.format(ex))
            _invalid = True
        else:
            if F_SERIAL_MIN in self.values:
                self.values.pop(F_SERIAL_MIN)
        finally:
            for _p_id in self._manager._addresses[self.short_addr.address]:
                if _p_id in self._manager._providers:
                    _provider = self._manager._providers[_p_id]
                    if _provider._dali_type == self._dali_type:
                        _provider._generate_def_value('Serial', _serial, invalid=_invalid, sig=sig)

    def HardwareVersion(self, sig=None):
        self.check_command_for_device()
        _hardware = ''
        _invalid = False
        try:
            _hardware = '.'.join(str(b) for b in self.read_memory_location(0, 0x13, 0x15))
        except BaseException as ex:
            logging.error('Error on HardwareVersion: \n {}'.format(ex))
            _invalid = True
        finally:
            for _p_id in self._manager._addresses[self.short_addr.address]:
                if _p_id in self._manager._providers:
                    _provider = self._manager._providers[_p_id]
                    if _provider._dali_type == self._dali_type:
                        _provider._generate_def_value('HardwareVersion', _hardware, invalid=_invalid, sig=sig)

    def GtinOem(self, sig=None):
        self.check_command_for_device()
        _gtin_oem = ''
        _invalid = False
        try:
            _gtin_oem = ''.join(hex(b)[2:].rjust(2, '0') for b in self.read_memory_location(1, 0x3, 0x9)).upper()
        except BaseException as ex:
            logging.error('Error on GtinOem: \n {}'.format(ex))
            _invalid = True
        finally:
            for _p_id in self._manager._addresses[self.short_addr.address]:
                if _p_id in self._manager._providers:
                    _provider = self._manager._providers[_p_id]
                    if _provider._dali_type == self._dali_type:
                        _provider._generate_def_value('GtinOem', _gtin_oem, invalid=_invalid, sig=sig)

    def SerialOem(self, sig=None):
        self.check_command_for_device()
        _serial_oem = ''
        _invalid = False
        try:
            _serial_oem = ''.join(hex(b)[2:].rjust(2, '0') for b in self.read_memory_location(1, 0x9, 0x11)).upper()
        except BaseException as ex:
            logging.error('Error on SerialOem: \n {}'.format(ex))
            _invalid = True
        finally:
            for _p_id in self._manager._addresses[self.short_addr.address]:
                if _p_id in self._manager._providers:
                    _provider = self._manager._providers[_p_id]
                    if _provider._dali_type == self._dali_type:
                        _provider._generate_def_value('SerialOem', _serial_oem, invalid=_invalid, sig=sig)

    def serialize(self) -> dict:
        d = {}
        if self.is_device:
            d['address'] = self.binding.addr.address
            for funit_type in [F_GTIN, F_SERIAL, F_GTIN_OEM, F_SERIAL_OEM, F_FIRMWARE, F_HARDWARE]:
                value = self.get_value(funit_type)
                if value is not None:
                    key = funit_type[0].lower() + funit_type[1:]
                    d[key] = value
                else:
                    if funit_type == F_GTIN or funit_type == F_SERIAL:
                        return {}
        return d


class RapidaDaliCombi(RapidaDaliProvider):
    @property
    def surveyable(self):
        return False

    @property
    def infoble(self):
        return False


class RapidaDaliCombiLight(RapidaDaliCombi):
    pass


class RapidaDaliCombiPresence(RapidaDaliCombi):
    pass
