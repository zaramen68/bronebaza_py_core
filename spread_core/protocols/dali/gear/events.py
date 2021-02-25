from spread_core.protocols.dali.address import Short, Group, InstanceNumber, InstanceType, InstanceGroup
from spread_core.protocols.dali.exceptions import EventError

# (default) Instance addressing, using instance type and number.
SCHEME_INST_TYPE_NUMBER = 0
# Device addressing, using short address and instance type.
SCHEME_ADDR_INST_TYPE = 1
# Device/instance addressing, using short address and instance number.
SCHEME_ADDR_INST_NUMBER = 2
# Device group addressing, using device group and instance type.
SCHEME_DEVICE_GROUP_INST_TYPE = 3
# Instance group addressing, using instance group and type.
SCHEME_INST_GROUP_TYPE = 4


class Event:
    _scheme_id = None
    short_addr = None
    instance_type = None
    instance_number = None
    device_group = None
    instance_group = None

    @staticmethod
    def of(frame):
        if not isinstance(frame, bytes):
            raise EventError('Frame must be bytes')
        elif len(frame) != 3:
            raise EventError('Frame size is {}. Expected frame size is 3'.format(len(frame)))

        if frame[0] >> 7 == 0x0:
            if frame[1] >> 7 == 0x0:
                return DeviceEvent(frame)
            elif frame[1] >> 7 == 0x1:
                return DeviceInstanceEvent(frame)
        elif frame[0] >> 6 == 0x2:
            if frame[1] >> 7 == 0x0:
                return DeviceGroupEvent(frame)
            elif frame[1] >> 7 == 0x1:
                return InstanceEvent(frame)
        elif frame[0] >> 6 == 0x3:
            if frame[1] >> 7 == 0x0:
                return InstanceGroupEvent(frame)

        raise EventError('Event message decoding error: {}<...>{}<..>'.format(bin(frame[0] >> 6)[2:].rjust(2, '0'),
                                                                              bin(frame[1] >> 7)[2:].rjust(2, '0')))

    def __init__(self, frame):
        self._frame = frame
        mask = ''.join(bin(b)[2:].rjust(8, '0') for b in frame)
        self.value = int(mask[14:], 2)

    @property
    def scheme_id(self):
        return self._scheme_id

    def __str__(self):
        attr = []
        if self.short_addr:
            attr.append(self.short_addr)
        if self.instance_type:
            attr.append(self.instance_type)
        if self.instance_number:
            attr.append(self.instance_number)
        if self.device_group:
            attr.append(self.device_group)
        if self.instance_group:
            attr.append(self.instance_group)
        return ('{}   [{}({})]' + ' {}' * len(attr)).format(self.value, self.__class__.__name__, self._scheme_id, *attr)


class DeviceEvent(Event):
    _scheme_id = 1

    def __init__(self, frame):
        super().__init__(frame)
        self.short_addr = Short(frame[0] >> 1)
        self.instance_type = InstanceType(frame[1] >> 2)


class DeviceInstanceEvent(Event):
    _scheme_id = 2

    def __init__(self, frame):
        super().__init__(frame)
        self.short_addr = Short(frame[0] >> 1)
        self.instance_number = InstanceNumber((frame[1] & 0x7f) >> 2)


class DeviceGroupEvent(Event):
    _scheme_id = 3

    def __init__(self, frame):
        super().__init__(frame)
        self.device_group = Group((frame[0] & 0x3f) >> 1)
        self.instance_type = InstanceType((frame[1] & 0x7f) >> 2)


class InstanceEvent(Event):
    _scheme_id = 0

    def __init__(self, frame):
        super().__init__(frame)
        self.instance_type = InstanceType((frame[0] & 0x3f) >> 1)
        self.instance_number = InstanceNumber((frame[1] & 0x7f) >> 2)


class InstanceGroupEvent(Event):
    _scheme_id = 0

    def __init__(self, frame):
        super().__init__(frame)
        self.instance_group = InstanceGroup((frame[0] & 0x3f) >> 1)
        self.instance_type = InstanceType((frame[1] & 0x7f) >> 2)


class SensorEvent:
    def __init__(self, value):
        self._value = value

    @property
    def value(self):
        return self._value


class PresenceEvent(SensorEvent):
    """
    00 0000 ---0 - No movement detected. Correspon ding trig ger is the ‘No movement’ trigger.
    00 0000 ---1 - Movement detected. Correspondin g tri gger is the ‘Movement’ trigger.
    00 0000 -00- - Vacant. The area has become vacant. Correspon ding trig ger is the ‘Vacant’ tri gger.
    00 0000 -10- - Still vacant. The area is sti l l vacant. The event occurs at reg ular interval s as long as
                        the vacant con di tion hol ds. Corresponding trigger is the ‘Repeat’ trig ger.
    00 0000 -01- - Occupied The area has become occupied. Correspondin g tri gger is the ‘Occupied ’ trigger.
    00 0000 -11- - Still occupied. The area is sti l l occupied. The event occurs at reg ular interval s as long as
                        the occupied con di tion holds. Correspondin g trig ger is the ‘Repeat’ trig ger.
    00 0000 0--- - Presence sensor. The current event is tri ggered by a presence based sensor.
    00 0000 1--- - Movement sensor. The current event is tri ggered by a movement based sensor.
    """

    _has_move = False
    _is_occupied = False
    _is_still_vacant = False
    _is_still_occupied = False
    _by_presence = False
    _by_movement = False

    def __init__(self, value):
        super(PresenceEvent, self).__init__(value)
        self._has_move = value & 0x1 == 0x1
        self._is_occupied = value & 0x2 == 0x2
        if value & 0x4 == 0x4:
            self._is_still_occupied = self._is_occupied
            self._is_still_vacant = not self._is_occupied
        self._by_presence = value & 0x8 == 0x0
        self._by_movement = value & 0x8 == 0x8
        pass

    def __str__(self):
        return '[{}]: {} ({})'.format(self.__class__.__name__, self.value, bin(self._value)[2:].rjust(5, '0'))

    @property
    def value(self):
        return self._has_move or self._is_occupied
