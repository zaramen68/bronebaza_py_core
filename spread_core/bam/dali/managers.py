from datetime import datetime

from spread_core.bam.dali import scanner, F_INSTANCES_INDEX, F_BUS
from spread_core.bam.dali.bindings import BindingDevice
from spread_core.bam.dali.providers.lights import RapidaDaliLight
from spread_core.bam.dali.providers.sensors import RapidaDaliSensor
from spread_core.bam.managers import Manager
from spread_core.mqtt import *
from spread_core.mqtt.variables import VariableJocket
from spread_core.protocols.dali import address
from spread_core.protocols.dali import command, frame
from spread_core.protocols.dali.exceptions import CommandGenerateError
from spread_core.protocols.dali.gear import events
from spread_core.protocols.dali.gear.general import _GearCommand
from spread_core.tools.settings import logging


class RapidaDali(Manager):
    def __init__(self, p_id, m_id):
        super().__init__(p_id, m_id)
        self._groups_1 = dict()
        self._groups_2 = dict()
        self._interface = None
        self._controller = None
        self._module = None
        self._channel = None
        self._class = None
        self._server_id = None
        self._on_scan = False
        self._scanner = None
        self._scan_time = None

    # говно-версия
    # def set_broker(self, mqttc, send_interface):
    #     super(RapidaDali, self).set_broker(mqttc, send_interface)
    #     self.use_retain = False
    # говно-версия END

    @property
    def scan_time(self):
        if self._scan_time is None:
            self._scan_time = datetime.now()
        return self._scan_time

    def parse(self, data):
        super(RapidaDali, self).parse(data)
        self._interface = data['attributes']['interface']
        try:
            self._controller = int(self._interface.split('/')[1])
        except:
            raise BaseException('data[attributes][interface] required as "[controller_type]/[controller_id]/[bus_type]"'
                                ' but it set as "{}"'.format(self._interface))
        self._module = data['attributes']['module']
        self._channel = data['attributes']['channel']
        self._class = data['attributes']['class']
        if self.send_interface:
            self.send_interface.set_bus_id(self._controller, self._module, self._channel)

    def add_provider(self, data, manager):
        super(RapidaDali, self).add_provider(data, manager)
        provider = self._providers[data['id']]
        if isinstance(provider.binding, BindingDevice):
            addr = provider.binding.addr.address
            if addr not in self._addresses:
                self._addresses[addr] = []
            self._addresses[provider.binding.addr.address].append(provider.id)

    def add_to_group(self, dali_type, group_id, provider_id):
        _groups = self._groups_1 if dali_type == 1 else self._groups_2
        if group_id not in _groups:
            _groups[group_id] = []
        if provider_id not in _groups[group_id]:
            _groups[group_id].append(provider_id)

    def get_group_members(self, dali_type, group_id):
        if dali_type == RapidaDaliLight._dali_type:
            if group_id in self._groups_1:
                return self._groups_1[group_id].copy()
        else:
            if group_id in self._groups_2:
                return self._groups_2[group_id].copy()
        return []

    def get_all_devices(self, dali_type):
        _res = []
        if dali_type == 1:
            for _provider in self._providers.values():
                if _provider.is_device and _provider._dali_type == dali_type:
                    _res.append(_provider.id)
        return _res

    def remove_from_group(self, dali_type, group_id, provider_id):
        _groups = self._groups_1 if dali_type == 1 else self._groups_2
        if group_id in _groups:
            if provider_id in _groups[group_id]:
                _groups[group_id].remove(provider_id)

    def on_ready(self):
        super(RapidaDali, self).on_ready()
        _bus = self.send_interface
        self.subscribe(mqtt.TopicDali(mqtt.DUMP, _bus.controller_id, _bus.module_id, _bus.channel))

    def on_exit(self):
        self._event.clear()
        self._external_cmd.clear()
        super(RapidaDali, self).on_exit()

    def on_command(self, topic, jocket):
        if self._scanner:
            return
        super(RapidaDali, self).on_command(topic, jocket)

    def survey(self):
        if self._scanner:
            return
        super(RapidaDali, self).survey()

    def on_external_command(self, command_frame):
        _data_str = ' '.join(hex(b)[2:].rjust(2, '0') for b in command_frame)
        _frame = frame.ForwardFrame(len(command_frame) * 8, command_frame)
        _cmd = command.from_frame(_frame)
        if not isinstance(_cmd, command.Command) or len(command_frame) < 2:
            logging.debug(f'EXTERNAL FRAME [{_data_str}]')
        elif isinstance(_cmd, _GearCommand):
            # DALI_1
            logging.debug(f'EXTERNAL DALI1 COMMAND [{_data_str}]: {_cmd}')

            if hasattr(_cmd, 'destination'):
                _provider = None
                for _p_id, _p in self._providers.items():
                    if isinstance(_p, RapidaDaliLight) and _p.binding.addr == _cmd.destination:
                        _provider = _p

                if _provider:
                    _p_ids = [_provider.id]
                elif isinstance(_cmd.destination, address.Group):
                    _p_ids = self.get_group_members(RapidaDaliLight._dali_type, _cmd.destination.group)
                elif isinstance(_cmd.destination, address.Broadcast):
                    _p_ids = self.get_all_devices(RapidaDaliLight._dali_type)
                else:
                    _p_ids = []

                for _p_id in _p_ids:
                    if _p_id in self._providers:
                        _provider = self._providers[_p_id]
                        if isinstance(_provider, RapidaDaliLight):
                            _provider.on_command_sended(_cmd)
        else:
            # DALI_2
            logging.debug(f'EXTERNAL DALI2 FRAME [{_data_str}] of {_cmd}')

    def on_event(self, event):
        provider = None
        if event.scheme_id == events.SCHEME_ADDR_INST_TYPE:
            if event.short_addr.address in self._addresses:
                for p_id in self._addresses[event.short_addr.address]:
                    _provider = self._providers[p_id]
                    if isinstance(_provider, RapidaDaliSensor) and _provider.instance.__eq__(event.instance_type):
                        provider = _provider
                        break
        elif event.scheme_id == events.SCHEME_ADDR_INST_NUMBER:
            if event.short_addr.address in self._addresses:
                for p_id in self._addresses[event.short_addr.address]:
                    _provider = self._providers[p_id]
                    if isinstance(_provider, RapidaDaliSensor) and _provider.get_value(F_INSTANCES_INDEX) == event.instance_number:
                        provider = _provider
                        break
        else:
            logging.warning('BAD EVENT of : {}'.format(event))
            return

        if provider is None:
            logging.debug(f'UNKNOWN DALI2 EVENT: {event}')
        else:
            provider.on_event(event)

    def scan(self, sig, data):
        if scanner.COMMAND not in data:
            raise CommandGenerateError('<<{}>> not in data'.format(scanner.COMMAND))
        if scanner.PARAMETERS not in data:
            raise CommandGenerateError('<<{}>> not in data'.format(scanner.PARAMETERS))
        if scanner.SCOPE not in data[scanner.PARAMETERS]:
            raise CommandGenerateError('<<{}>> not in data[{}]'.format(scanner.PARAMETERS, scanner.SCOPE))

        form = data[scanner.COMMAND]                                        # [scan, construct, extend]
        dali1 = data[scanner.PARAMETERS][scanner.SCOPE] != scanner.DALI2    # [dali1, dali2, all]
        dali2 = data[scanner.PARAMETERS][scanner.SCOPE] != scanner.DALI1
        # Omg, but yet...))
        #########
        intersect = scanner.INTERSECT not in data[scanner.PARAMETERS] or not data[scanner.PARAMETERS][scanner.INTERSECT]
        #########
        _scanner = scanner.DaliScanner(self, sig, form, dali1=dali1, dali2=dali2, intersect=intersect)
        self._scanner = _scanner

        try:
            self.send_interface.send(device.StartQuiescentMode(address.Broadcast()))
            scope = _scanner.start()
        except BaseException as ex:
            logging.exception(ex)
        finally:
            self._scan_time = datetime.now()
            self.send_interface.send(gear.Terminate())
            self.send_interface.send(device.Terminate())
            self.send_interface.send(device.StopQuiescentMode(address.Broadcast()))
            self._scanner.pubish_progress(100)
            self._scanner = None
            
    def GetScan(self, sig):
        funit_type = F_BUS
        funit = self.get_funit(funit_type)
        value = {"managerID": self.id,
                 "managerType": self.__class__.__name__,
                 "scanData": dict(devices=[], devices2=[]),
                 "scanIndex": 0,
                 "scanName": "",
                 "scanTime": str(self.scan_time).replace(' ', 'T')}

        for addr, ids in self._addresses.items():
            device2 = None
            for p_id in ids:
                if p_id in self._providers:
                    provider = self._providers[p_id]
                    d = provider.serialize()
                    if d:
                        if isinstance(provider, RapidaDaliLight):
                            value['scanData']['devices'].append(d)
                        elif isinstance(provider, RapidaDaliSensor):
                            if device2 is None:
                                device2 = d
                                device2['instances'] = []
                            inst = provider.serialize_instance()
                            if inst:
                                device2['instances'].append(inst)

            if device2:
                value['scanData']['devices2'].append(device2)

        jocket = VariableJocket.create_data(self.id, funit['id'], 'state', value, sig.key)
        jocket.data['data'] = value
        topic = mqtt.TopicReply(self.project_id, sig.session_id)
        self.publish(topic, jocket, retain=False)
