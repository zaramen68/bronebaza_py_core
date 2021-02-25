from spread_core.errors.project_errors import ProjectError
from spread_core.protocols.dali.address import Short, Broadcast, Group, BroadcastUnaddressed

BINDING = 'Binding'
DEVICE = 'Device'
GROUP = 'Group'
BROADCAST = 'Broadcast'
UNADDRESSED = 'Unaddressed'

ALL = [DEVICE, GROUP, BROADCAST, UNADDRESSED]


def of(data):
    if DEVICE in data or data[BINDING.lower()] == DEVICE:
        return BindingDevice(data)
    elif data[BINDING.lower()] == GROUP:
        return BindingGroup(data)
    elif data[BINDING.lower()] == BROADCAST:
        return BindingBroadcast(data)
    elif data[BINDING.lower()] == UNADDRESSED:
        return BindingUnaddressed(data)
    else:
        raise ProjectError('Unknown binding', binding=data)


class Binding:
    _type = None

    def __init__(self, data):
        self.addr = None
        if 'def_' + GROUP.lower() in data:
            self.def_group = data['def_' + GROUP.lower()]
        if 'def_' + DEVICE.lower() in data:
            self.def_device = data['def_' + DEVICE.lower()]
        if 'def_' + BINDING.lower() in data:
            self.def_binding = data['def_' + BINDING.lower()]

    def override_addr(self, new_addr):
        raise NotImplementedError()

    def __str__(self):
        return str(self.addr)

    @property
    def b_type(self):
        return self._type


class BindingDevice(Binding):
    _type = DEVICE

    def __init__(self, data):
        super().__init__(data)
        self.addr = Short(data[self._type.lower()])

    def set_addr(self, new_addr_int):
        self.addr = Short(new_addr_int)


class BindingGroup(Binding):
    _type = GROUP

    def __init__(self, data):
        super().__init__(data)
        self.addr = Group(data[self._type.lower()])

    def set_addr(self, new_addr_int):
        self.addr = Group(new_addr_int)


class BindingBroadcast(Binding):
    _type = BROADCAST

    def __init__(self, data):
        super().__init__(data)
        self.addr = Broadcast()


class BindingUnaddressed(Binding):
    _type = UNADDRESSED

    def __init__(self, data):
        super().__init__(data)
        self.addr = BroadcastUnaddressed()
