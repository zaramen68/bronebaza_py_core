from spread_core.protocols.dali.exceptions import NotConnected, DeviceAlreadyBound, DuplicateDevice, BadDevice


MAX_DEVICE = 64


class Device0(object):
    """Any DALI slave device that has been configured with a short address."""

    def __init__(self, address, bus=None, err=False, long=0):
        if not isinstance(address, int) or address < 0 or address > 63:
            raise ValueError("address must be an integer in the range 0..63")
        self.address = address
        self.bus = None
        self.err = err
        self._long = long
        self._types = None
        self._gtin = None
        self._serial = None
        self._fv = None
        self._hv = None
        self._gtin_oem = None
        self._serial_oem = None
        if bus:
            self.bind(bus)

    def bind(self, bus):
        """Bind this device object to a particular DALI bus."""
        bus.add_device(self)

    def types(self):
        return []

    @property
    def long(self):
        return self._long

    def __repr__(self):
        return str(self)

    def types(self):
        raise NotImplementedError()

    def gtin(self, i):
        if self._gtin is None:
            try:
                self._gtin = ''.join(hex(b)[2:].rjust(2, '0') for b in self.bus.read_memory_location(i, self.address, 0, 0x3, 0x9)).upper()
            finally:
                return self._gtin

    def serial(self, i):
        if self._serial is None:
            try:
                self._serial = ''.join(hex(b)[2:].rjust(2, '0') for b in self.bus.read_memory_location(i, self.address, 0, 0xb, 0x13)).upper()
            finally:
                return self._serial

    def fv(self, i):
        if self._fv is None:
            try:
                self._fv = ''.join(hex(b)[2:].rjust(2, '0') for b in
                                   self.bus.read_memory_location(i, self.address, 0, 0x9, 0xb)).upper()
            finally:
                return self._fv

    def hv(self, i):
        if self._hv is None:
            try:
                self._hv = ''.join(hex(b)[2:].rjust(2, '0') for b in self.bus.read_memory_location(i, self.address, 0, 0x13, 0x15)).upper()
            finally:
                return self._hv

    def gtin_oem(self, i):
        if self._gtin_oem is None:
            try:
                self._gtin_oem = ''.join(hex(b)[2:].rjust(2, '0') for b in self.bus.read_memory_location(i, self.address, 1, 0x3, 0x9)).upper()
            finally:
                return self._gtin_oem

    def serial_oem(self, i):
        if self._serial_oem is None:
            try:
                self._serial_oem = ''.join(hex(b)[2:].rjust(2, '0') for b in self.bus.read_memory_location(i, self.address, 1, 0x9, 0x11)).upper()
            finally:
                return self._serial_oem


class Bus0(object):
    """A DALI bus."""
    _dali_type = 0
    _all_addresses = range(MAX_DEVICE)
    _h = 0x0
    _m = 0x0
    _l = 0x0

    def __init__(self, interface, on_progress, on_found):
        self._devices = {}
        self._bus_scanned = False  # Have we scanned the bus for devices?
        self._interface = interface
        self._on_progress = on_progress
        self._on_found = on_found

    @property
    def dali_type_int(self):
        return self._dali_type

    @property
    def dali_type(self):
        return 'dali{}'.format(self._dali_type)

    def fill_addresses(self):
        raise NotImplementedError()

    def get_interface(self):
        if not self._interface:
            raise NotConnected()
        return self._interface

    def get_device(self, addr):
        if addr in self._devices:
            return self._devices[addr]

    def add_device(self, device):
        if device.bus and device.bus != self:
            raise DeviceAlreadyBound()
        if device.address in self._devices:
            raise DuplicateDevice()
        if not isinstance(device.address, int) or device.address < 0 or device.address > 63:
            raise BadDevice("device address is invalid")
        self._devices[device.address] = device
        device.bus = self

    def unused_addresses(self):
        """Return all short addresses that are not in use."""
        # used_addresses = sets.ImmutableSet(self._devices.keys())
        return self._all_addresses - self.used_addresses()

    def used_addresses(self):
        return self._devices.keys()

    def scan(self) -> list:
        raise NotImplementedError()

    def set_search_addr(self, addr):
        raise NotImplementedError()

    def find_next(self, low, high):
        raise NotImplementedError()

    def assign_short_addresses(self, param, lock_addresses=[]):
        raise NotImplementedError()

    def program_short_address(self, long, short):
        raise NotImplementedError()

    @staticmethod
    def read_memory_location(i, owner_addr, bank_id, start_address, end_address):
        raise NotImplementedError()
