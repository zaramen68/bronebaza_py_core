import sys

from spread_core import mqtt
from spread_core.bam.entities import Entity
from spread_core.mqtt.variables import STATE, VariableJocket
from spread_core.tools import settings
from spread_core.tools.settings import logging

logging.basicConfig(format=u'%(levelname)-8s [%(asctime)s]  %(message)s',
                    level=logging.DEBUG if sys.argv[len(sys.argv) - 1] == 'debug' else logging.INFO,
                    stream=sys.stdout)


class UObj:
    def __init__(self, attr_name, val, sig=None):
        self.value = dict()
        self._sig = sig
        if isinstance(val, dict):
            self.value[attr_name] = val
        self.value[attr_name] = val

    @property
    def sig(self):
        return self._sig

    def __str__(self):
        res = []
        for k, v in self.value.items():
            res.append('{}={}'.format(k, v))
        return ', '.join(res)


class Provider(Entity):
    def __init__(self, data):
        super(Provider, self).__init__(data['id'])
        self._manager_id = data['managerID']
        self._manager = None
        self._invalid_values = []
        self._valid = True

    def is_dumped(self, key):
        return key in self._dumped or not self.is_device

    @property
    def manager(self):
        return self._manager

    def get_address(self, funit_id):
        return mqtt.ProviderAddress.of(self, funit_id)

    def publish_all(self, sig=None):
        for funit_type, value in self.values.items():
            funit = self.get_funit(funit_type)
            if funit:
                class_id = funit['id']
                jocket = VariableJocket.create_data(id=self.id, cl=class_id, action='state', val=value)
                if sig:
                    jocket.key = sig.key
                state_topic = mqtt.TopicState(self._manager.project_id, self.get_address(funit_type))
                self._manager.publish(state_topic, jocket.pack(), retain=False)

    @property
    def surveyable(self):
        return True

    @property
    def infoble(self):
        return True

    @property
    def is_device(self):
        return True

    @property
    def is_group(self):
        return False

    @property
    def is_broadcast(self):
        return False

    @property
    def is_valid(self):
        return self._valid

    def set_manager(self, manager):
        self._manager = manager

    def on_update(self, funit_type, data, retain=True, invalid=False):
        raise NotImplementedError()

    def on_command_sended(self, cmd):
        pass

    def on_command(self, topic, jocket):
        raise NotImplementedError()

    def on_queue(self):
        pass

    def send(self, cmd):
        return self._manager.send_interface.send(cmd)

    def get_bindings(self):
        pass

    def on_command_prepared(self, *commands):
        self.manager.add_command(self, *commands)

    def request(self, cmd, *args, **kwargs):
        try:
            response = self._manager.send_interface.send(cmd, *args, **kwargs)
        except BaseException as ex:
            logging.exception(ex)
        else:
            if response and response.value is not None:
                if cmd.sig and cmd.sig.is_not_empty:
                    response.set_signature(cmd.sig)
                for funit_type in cmd.funit_type:
                    try:
                        self.on_request_answer(funit_type, response)
                    except BaseException as ex:
                        logging.exception(ex)

    def on_request_answer(self, funit_type, response):
        self.on_update(funit_type, response)

    def set_valid(self, validity):
        self._valid = validity

    def _generate_def_value(self, funit_type, value, invalid=False, sig=None):
        if value is None or value == '':
            funit = self.get_funit(funit_type)
            if funit:
                if mqtt.DEF_VAL in funit:
                    value = funit[mqtt.DEF_VAL]
                elif mqtt.VARIANTS in funit:
                    value = funit[mqtt.VARIANTS][0]
                else:
                    value = self.get_value(funit_type, funit[STATE]())
                    if value is None:
                        value = funit[STATE]()
        self.on_update(funit_type, UObj(funit_type, value, sig=sig), retain=True, invalid=invalid)

    def on_survey(self):
        raise NotImplementedError()

    def get_info(self):
        raise NotImplementedError()

    def check_valid(self):
        self._valid = True

    def on_exit(self):
        pass

    def override_info(self):
        for funit_type, value in settings.get_dump_entity(self).items():
            self._generate_def_value(funit_type, value)

    def get_funit(self, funit_type):
        if self._manager.__class__.__name__ in mqtt.classifier:
            if self.__class__.__name__ in mqtt.classifier[self._manager.__class__.__name__]:
                if funit_type is None:
                    return mqtt.classifier[self._manager.__class__.__name__][self.__class__.__name__]
                if funit_type in mqtt.classifier[self._manager.__class__.__name__][self.__class__.__name__]:
                    return mqtt.classifier[self._manager.__class__.__name__][self.__class__.__name__][funit_type]
        return None
