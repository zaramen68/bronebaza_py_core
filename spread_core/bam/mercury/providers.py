import json
from datetime import datetime

import spread_core.mqtt.variables
from spread_core import mqtt
from spread_core.bam.providers import Provider
from spread_core.errors.project_errors import ProjectError
from spread_core.protocols.mercury.commands import *


class MercuryElectricMeter(Provider):
    def __init__(self, data):
        super(MercuryElectricMeter, self).__init__(data)
        self.address = data['attributes']['address']
        self.name = data['name']
        self.cmds = dict()
        self.passwords = dict()
        for i in range(1, 4):
            if 'password{}'.format(i) in data['attributes']:
                self.passwords[i] = data['attributes']['password{}'.format(i)]
        self._session_time = 230

        self._deprecate_time = dict()
        self._deprecate_time[1] = 0
        self._deprecate_time[2] = 0
        self._invalid = False

    def on_auth(self, level):
        if level in self._deprecate_time:
            self._deprecate_time[level] = datetime.now().timestamp()

    def check_access_level(self, cmd):
        ts = datetime.now().timestamp()
        level = cmd.access_level
        if level > 0 and level in self._deprecate_time and ts - self._deprecate_time[level] >= self._session_time:
            level = cmd.access_level
            r = self._manager.send_interface.send(OpenSession(addr=self.address,
                                                              s_type=level,
                                                              password=self.passwords[level]))
            if r is None or not r.success:
                raise ProjectError("Access error for {}".format(self.address))

            self.on_auth(level)

    def on_command(self, topic, jocket):
        args = []
        kwargs = dict()
        absent = []
        act = jocket.action
        funit = topic.entity_addr.funit
        if act in funit:
            if 'params' in funit[act]:
                if 'data' in jocket.data:
                    for p in funit[act]['params']:
                        if p in jocket.data['data']:
                            kwargs[p] = jocket.data['data'][p]
                        else:
                            absent.append(p)
                else:
                    absent.append('data')
            else:
                if act == mqtt.variables.SET:
                    from spread_core.protocols.mercury import SetTransformRate
                    if funit[act]['cmd'] == SetTransformRate:
                        vls = SetTransformRate._funit_type
                        kwargs[topic.entity_addr.funit_type] = jocket.value
                        if vls[0] not in kwargs:
                            kwargs[vls[0]] = self.values[vls[0]]
                        if vls[1] not in kwargs:
                            kwargs[vls[1]] = self.values[vls[1]]

                    else:
                        args.append(jocket.value)
        else:
            absent.append('action')

        if len(absent) > 0:
            topic = mqtt.TopicReply(self._manager.project_id, topic.session_id)
            if 'data' in jocket.data:
                jocket.data.pop('data')
            jocket.data['error'] = dict(code=123, message='{} are absent in jocket'.format(absent))
            self._manager.publish(topic, jocket.pack())
        else:
            get_cmd_class = funit[act]['cmd']
            cmd = get_cmd_class(self.address, *args, **kwargs)
            cmd._funit_type = [topic.entity_addr.funit_type]
            if act == mqtt.variables.GET:
                self.cmds[cmd] = topic.session_id
            elif act == act == mqtt.variables.SET:
                self.cmds[cmd] = jocket.value

            self._manager.add_command(self, cmd)

    def on_update(self, funit_type, data, retain=True, invalid=False):
        self.on_auth(data.cmd.access_level)
        entity_addr = self.get_address(funit_type)
        p_data = data.cmd.res_pack(funit_type)
        need_state = False
        if isinstance(data.cmd, WriteCommand):
            if data.cmd not in self.cmds:
                return None, None
            val = self.cmds.pop(data.cmd)
            self.set_value(funit_type, val)
            need_state = True
        elif len(p_data) == 1:
            if funit_type in data.value:
                val = data.value[funit_type]
            else:
                val = data.value
            if funit_type not in self.values or self.values[funit_type] != val:
                self.set_value(funit_type, val)
                need_state = True
        else:
            p_name = p_data
            val = p_name.pop('value')
            p_name = str(p_name)
            if funit_type not in self.values:
                self.values[funit_type] = dict()
            if p_name not in self.values[funit_type] or self.values[funit_type][p_name] != val:
                self.values[funit_type][p_name] = val
                need_state = True

        if data.cmd in self.cmds:
            topic = mqtt.TopicReply(self._manager.project_id, self.cmds.pop(data.cmd))
        elif need_state:
            topic = mqtt.TopicState(self._manager.project_id, entity_addr)
        else:
            return

        packet = dict(address=dict(id=self.id),
                      action='state',
                      timestamp=str(datetime.now()).replace(' ', 'T'),
                      data=p_data)
        packet['address']['class'] = entity_addr.funit['id']
        packet['data']['value'] = val
        packet = json.dumps(packet)
        self._manager.publish(topic, packet, retain=isinstance(topic, mqtt.TopicState))

    def request(self, cmd):
        self.check_access_level(cmd)
        super(MercuryElectricMeter, self).request(cmd)

    def on_survey(self):
        addr = self.address
        for phase in range(0, 4):
            for power_id in range(0, 3):
                self._manager.add_survey(self, AUXPower(addr=addr, power_id=power_id, phase=phase))
            self._manager.add_survey(self, AUXPowerRate(addr=addr, phase=phase))
            if phase > 0:
                self._manager.add_survey(self, AUXAmperage(addr=addr, phase=phase))
                self._manager.add_survey(self, AUXVoltage(addr=addr, phase=phase))
                self._manager.add_survey(self, AUXAngle(addr=addr, phase=phase))
            else:
                self._manager.add_survey(self, AUXFrequency(addr=addr))
                self._manager.add_survey(self, TransformRate(addr=addr))

    def get_info(self):
        funit_type = 'Info'
        funit = mqtt.classifier[self._manager.__class__.__name__][self.__class__.__name__][funit_type]
        info = dict(address=self.address, name=self.name)
        info_arr = [
            SerialCommand(self.address),
            CurrentDateTime(self.address)
        ]
        for cmd in info_arr:
            try:
                self.check_access_level(cmd)
                r = self._manager.send_interface.send(cmd)
                info[cmd.funit_type[0]] = r.value
            except BaseException as ex:
                # ToDo exceptions logging
                # logging.exception(ex)
                info[cmd.funit_type[0]] = None

        packet = dict(address=dict(id=self.id),
                      action='state',
                      timestamp=str(datetime.now()).replace(' ', 'T'),
                      data=dict(value=info))
        packet['address']['class'] = funit['id']
        packet = json.dumps(packet)
        topic = mqtt.TopicState(self._manager.project_id, self.get_address(funit_type))
        self._manager.publish(topic, packet, retain=True)
