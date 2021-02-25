"""Declaration of base types for dali commands and their responses."""

from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from spread_core.protocols.dali import address
from spread_core.protocols.dali import frame
from spread_core.protocols.dali.compat import add_metaclass, python_2_unicode_compatible
from spread_core.protocols.dali.exceptions import MissingResponse
from spread_core.protocols.dali.exceptions import ResponseError


class CommandTracker(type):
    """Metaclass keeping track of all the types of Command we understand.

    Commands that have names starting with '_' are treated as abstract
    base classes that will never be instantiated because they do not
    correspond to a DALI frame.
    """

    def __init__(cls, name, bases, attrs):
        if not hasattr(cls, '_commands'):
            cls._commands = []
        else:
            if cls.__name__[0] != '_':
                cls._commands.append(cls)

    @classmethod
    def commands(cls):
        """
        :return: List of known commands if there's any
        """
        return cls._commands


class CommandSignature:
    def __init__(self, key=None, session_id=None):
        self._key = key
        self._session_id = session_id

    @property
    def key(self):
        return self._key

    def set_key(self, key):
        self._key = key

    @property
    def session_id(self):
        return self._session_id

    def set_session_id(self, session_id):
        self._session_id = session_id

    @property
    def is_not_empty(self):
        return self._key is not None or self._session_id is not None

    def __str__(self):
        return 's_id: {}; key: {}'.format(self.session_id, self.key)


@python_2_unicode_compatible
class Response(object):
    """Some DALI commands cause a response from the addressed devices.

    The response is either an 8-bit backward frame encoding 8-bit data
    or 0xff for "Yes", or a lack of response encoding "No".  If
    multiple devices respond at once the backward frame may be
    received with a framing error; this shall be interpreted as "more
    than one device answered "Yes".

    Initialise this class by passing a BackwardFrame object, or None
    if there was no response.
    """
    _expected = False
    _error_acceptable = False

    def __init__(self, val):
        if val is not None and not isinstance(val, (frame.BackwardFrame, frame.BackwardModuleError)):
            raise TypeError("Response must be passed None or a BackwardFrame")
        self._value = val
        self._sig = None

    def set_signature(self, sig):
        self._sig = sig

    @property
    def sig(self):
        return self._sig

    @property
    def value(self):
        # if self._value is None and self._expected:
        #     raise MissingResponse()
        if self._value and self._value.error and not self._error_acceptable:
            raise ResponseError()
        return self._value

    def __str__(self):
        try:
            return "{}".format(self.value)
        except MissingResponse or ResponseError as e:
            return "{}".format(e)


class YesNoResponse(Response):
    @property
    def value(self):
        return self._value is not None and (not self._value.error or self._error_acceptable)


class YesNoErrorResponse(YesNoResponse):
    _error_acceptable = True


class BitmapResponseBitDict(type):
    """Metaclass adding dict of status bits."""

    def __init__(cls, name, bases, attrs):
        if hasattr(cls, "bits"):
            bd = {}
            bit = 0
            for b in cls.bits:
                if b:
                    mangled = b.replace(' ', '_').replace('-', '')
                    bd[mangled] = bit
                bit = bit + 1
            cls._bit_properties = bd


@python_2_unicode_compatible
@add_metaclass(BitmapResponseBitDict)
class BitmapResponse(Response):
    """A response that consists of several named bits.

    Bits are listed in subclasses with the least-sigificant bit first.
    """
    _expected = True
    bits = []

    @property
    def status(self):
        if self._value is None:
            raise MissingResponse()
        if self._value.error:
            return ["response received with framing error"]
        v = self._value[7:0]
        l = []
        for b in self.bits:
            if v & 0x01 and b:
                l.append(b)
            v = (v >> 1)
        return l

    @property
    def status_full(self):
        d = {}
        v = self._value[7:0]
        for b in self.bits:
            b_name = b.strip()
            while ' ' in b_name:
                space = b_name.index(' ')
                if len(b_name) - 1 > space:
                    b_name = b_name[:space] + b_name[space + 1].upper() + b_name[space + 2:]
                else:
                    break

            d[b_name] = bool(v & 0x01 and b)
            v = (v >> 1)
        return d

    @property
    def error(self):
        if self._value is None:
            return False
        return self._value.error

    def __getattr__(self, name):
        if name in self._bit_properties:
            if self._value is None:
                return
            if self._value.error:
                return
            return self._value[self._bit_properties[name]]
        raise AttributeError

    def __str__(self):
        try:
            # return ",".join(self.status)
            return "; ".join(f'{k}={v}' for k, v in self.status_full.items())
        # XXX: be more explicit which exception to catch
        except Exception as e:
            return "{}".format(e)


STATE_SENDED = 1
STATE_PRECOMMITED = 2
STATE_COMMITED = 3
STATE_SUCCESS = 4


@python_2_unicode_compatible
@add_metaclass(CommandTracker)
class  Command(object):
    """A command frame.

    Subclasses must provide a class method "from_frame" which, when
    passed a Frame returns a new instance of the class corresponding
    to that command, or "None" if there is no match.
    """

    # Override this as appropriate
    _framesize = 0
    _funit_type = []

    # The following flags correspond to the columns in tables 15 and
    # 16 of IEC 62386-102 and tables 21 and 22 of IEC 62386-103.
    # Override them in subclasses if there is a tick in the
    # appropriate column.
    _appctrl = False
    _inputdev = False
    _uses_dtr0 = False
    _uses_dtr1 = False
    _uses_dtr2 = False
    _response = None
    _sendtwice = False
    _force_answer = False
    _commit_state = False
    _notified = False
    _levels_dependent = False
    _attempts = 1

    # 16-bit frames may be interpreted differently if they are
    # preceded by the EnableDeviceType command.  If a command needs
    # EnableDeviceType(foo) to be sent first, override _devicetype to
    # foo.  This parameter is ignored for all other frame lengths.
    _devicetype = 0

    def __init__(self, f):
        assert isinstance(f, frame.ForwardFrame)
        self._data = f
        self._sig = CommandSignature()
        self.attempt = 0

    @property
    def sig(self):
        return self._sig

    @property
    def funit_type(self):
        return self._funit_type

    @classmethod
    def from_frame(cls, f, devicetype=0):
        """Return a Command instance corresponding to the supplied frame.

        If the device type the command is intended for is known
        (i.e. the previous command was EnableDeviceType(foo)) then
        specify it here.

        :parameter frame: a forward frame
        :parameter devicetype: type of device frame is intended for

        :returns: Return a Command instance corresponding to the
        frame.  Returns None if there is no match.
        """
        if cls != Command:
            return

        for dc in cls._commands:
            if dc._devicetype != devicetype:
                continue
            r = dc.from_frame(f)
            if r:
                return r

        # At this point we can simply wrap the frame.  We don't know
        # what kind of command this is (config, query, etc.) so we're
        # unlikely ever to want to transmit it!
        return cls(f)

    @property
    def frame(self):
        """The forward frame to be transmitted for this command."""
        return self._data

    # XXX rename to send_twice ?
    @property
    def is_config(self):
        """Is this a configuration command?  (Does it need repeating to
        take effect?)
        """
        return self._sendtwice

    @property
    def is_forced(self):
        """Is this a command are forced?  (Does answer is obligatory?)
        """
        return self._force_answer

    @property
    def is_query(self):
        """Does this command return a result?"""
        return self._response is not None

    @property
    def is_send_notify(self):
        """ Does need notify on respone"""
        return self._notified

    @property
    def is_levels_dependent(self):
        """ Does level depend from command"""
        return self._levels_dependent

    @property
    def need_retry(self):
        """ Does need retry on fail"""
        return hasattr(self, 'attempt') and self.attempt < self._attempts

    @property
    def device_type(self):
        return self._devicetype

    @property
    def response(self):
        """If this command returns a result, use this class for the response.
        """
        return self._response

    @staticmethod
    def _check_destination(destination):
        """Check that a valid destination has been specified.

        destination can be a dali.bus.Device object with
        address_obj attribute, a dali.address.Address object with
        add_to_frame method, or an integer which will be wrapped in a
        dali.address.Address object.
        """
        if hasattr(destination, 'address_obj'):
            destination = destination.address_obj
        if isinstance(destination, int):
            destination = address.Short(destination)
        if hasattr(destination, 'add_to_frame'):
            return destination
        raise ValueError('destination must be an integer, dali.bus.Device '
                         'object or dali.address.Address object')

    def state(self):
        if self._commit_state == 1:
            return 'Sended'
        elif self._commit_state == 2:
            return 'Sended'
        elif self._commit_state == 2:
            return 'Sended'

    def on_send(self):
        if hasattr(self, 'attempt'):
            self.attempt += 1
        self._commit_state = STATE_SENDED

    @property
    def is_commited(self):
        return self._commit_state >= STATE_COMMITED

    def on_commit(self):
        if self._commit_state != STATE_PRECOMMITED and self._sendtwice:
            self._commit_state = STATE_PRECOMMITED
        elif self.is_query:
            self._commit_state = STATE_COMMITED
        else:
            self._commit_state = STATE_SUCCESS

    def on_response(self):
        self._commit_state = STATE_SUCCESS

    def __str__(self):
        joined = ":".join(
            "{:02x}".format(c) for c in self._data.as_byte_sequence)
        return "({0}){1}".format(type(self), joined)


from_frame = Command.from_frame
