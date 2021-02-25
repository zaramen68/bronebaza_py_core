from __future__ import division
from __future__ import unicode_literals

import time

from spread_core.protocols.dali.address import Short
from spread_core.protocols.dali.bus.bus0 import Bus0, Device0, MAX_DEVICE
from spread_core.protocols.dali.exceptions import NoFreeAddress
from spread_core.protocols.dali.gear import general as gear
from spread_core.tools.settings import logging


class Device1(Device0):
    """Any DALI slave device that has been configured with a short address."""

    def __init__(self, address, bus=None, err=False, long=0):
        super(Device1, self).__init__(address, bus, err, long)
        self.type_id = None
        self.type_name = 'unknown device Dali'

    def types(self):
        return [self.type_id]

    def set_type(self, type_id, type_name):
        if not isinstance(type_id, gear.QueryDeviceTypeResponse):
            self.type_id = type_id
            self.type_name = type_name

    def __str__(self):
        return '{}'. format(self.type_name) + ('ERR' if self.err else '')


"""A DALI_1 bus."""


class Bus1(Bus0):
    _dali_type = 1

    def fill_addresses(self):
        if not self._bus_scanned:
            i = self.get_interface()
            for addr in range(0, MAX_DEVICE):
                try:
                    response = i.send(gear.QueryDeviceType(Short(addr)))
                    if addr not in self._devices:
                        if response and response.value:
                            Device1(address=addr, bus=self)
                except BaseException as ex:
                    logging.exception(ex)

    def scan(self, l=None) -> list:
        """Scan the bus for devices and ensure there are device objects for
        each discovered device.
        """
        result = []
        i = self.get_interface()
        _counter = 0
        if l is None:
            l = range(0, MAX_DEVICE)
        for addr in l:
            try:
                short = Short(addr)
                response = i.send(gear.QueryDeviceType(short))
                if response is not None and response.value is not None:
                    if response.value.as_integer == 255:
                        types = []
                        while True:
                            tp = i.send(gear.QueryNextDeviceType(short))
                            try:
                                if tp.value.as_integer == 0xfe:
                                    break
                                else:
                                    types.append(tp.value.as_integer)
                            except:
                                types = [response.value.as_integer]
                                break
                    else:
                        types = [response.value.as_integer]
                    if addr not in self._devices:
                        dev = Device1(address=addr, bus=self)
                    else:
                        dev = self._devices[addr]
                    dev.set_type(response.value.as_integer, str(response))
                    obj = {
                        'address': addr,
                        'gtin': dev.gtin(i),
                        'types': types
                    }
                    result.append(obj)
                    self._on_found(self._dali_type, obj, _counter)
                    _counter += 1
                self._on_progress(l.index(addr) + 1)
            except BaseException as ex:
                logging.exception(ex)
        self._bus_scanned = True
        return result

    def set_search_addr(self, addr):
        i = self.get_interface()

        h = (addr >> 16) & 0xff
        if self._h != h:
            self._h = h
            i.send(gear.SetSearchAddrH(h))

        m = (addr >> 8) & 0xff
        if self._m != m:
            self._m = m
            i.send(gear.SetSearchAddrM(m))

        l = addr & 0xff
        if self._l != l:
            self._l = l
            i.send(gear.SetSearchAddrL(l))

    def find_next(self, low, high):
        """Find the ballast with the lowest random address.  The caller
        guarantees that there are no ballasts with an address lower
        than 'low'.

        If found, returns the random address.  SearchAddr will be set
        to this address in all ballasts.  The ballast is not
        withdrawn.

        If not found, returns None.
        """
        i = self.get_interface()
        self.set_search_addr(high)
        if low == high:
            response = i.send(gear.Compare())
            if response.value is True:
                return low
            return None
        time.sleep(0.1)
        response = i.send(gear.Compare())
        if response is None or response.value is False:
            response = i.send(gear.Compare())
        if response is None or response.value is True:
            midpoint = (low + high) // 2
            return self.find_next(low, midpoint) \
                or self.find_next(midpoint + 1, high)

    def assign_short_addresses(self, broadcast=True, lock_addresses=[]):
        """Search for devices on the bus with no short address allocated, and
        allocate each one a short address from the set of unused
        addresses.
        """
        # if not self._bus_scanned:
        #     self.scan()
        address = None
        new_devices = []
        addrs = list(self.unused_addresses() - lock_addresses)
        i = self.get_interface()
        i.send(gear.Terminate())
        i.send(gear.Initialise(broadcast, address))
        i.send(gear.Randomise())
        # Randomise may take up to 100ms
        time.sleep(0.1)
        low = 0
        high = 0xffffff
        while low is not None:
            low = self.find_next(low, high)
            if low is not None:
                if addrs:
                    new_addr = addrs.pop(0)
                    i.send(gear.ProgramShortAddress(new_addr))
                    r = i.send(gear.QueryShortAddress())
                    i.send(gear.Withdraw())
                    err = r.value.as_integer >> 1 != new_addr
                    Device1(address=new_addr, bus=self, err=err)
                    new_devices.append(new_addr)
                    self._on_progress(len(self._devices))
                else:
                    i.send(gear.Terminate())
                    raise NoFreeAddress()
                low = low + 1
        return new_devices

    def find_repetitive_short_addresses(self):
        """Search for devices on the bus with a repetitive short address.
        """
        devices = dict()
        i = self.get_interface()
        i.send(gear.Terminate())
        i.send(gear.Initialise(True))
        i.send(gear.Randomise())
        time.sleep(0.1)
        low = 0
        high = 0xffffff
        while low is not None:
            low = self.find_next(low, high)
            if low is not None:
                r = i.send(gear.QueryShortAddress())
                i.send(gear.Withdraw())
                addr = r.value.as_integer >> 1
                if addr not in devices:
                    devices[addr] = []
                devices[addr].append(Device1(addr, long=low))
                self._on_progress(len(devices))
                low = low + 1
        return devices

    def program_short_address(self, long, short):
        self.set_search_addr(long)
        i = self.get_interface()
        if i:
            i.send(gear.ProgramShortAddress(short))

    @staticmethod
    def read_memory_location(i, entity_addr, bank_id, start_address, end_address):
        result = b''
        i.send(gear.DTR1(bank_id))
        i.send(gear.DTR0(start_address))
        for _dtr0 in range(start_address, end_address):
            res = i.send(gear.ReadMemoryLocation(entity_addr))
            if res.value:
                result += res.value.pack
            else:
                return result

        return result
