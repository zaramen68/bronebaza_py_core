from __future__ import division
from __future__ import unicode_literals

import time

from spread_core.protocols.dali.address import Short, InstanceNumber, InstanceType
from spread_core.protocols.dali.bus.bus0 import Device0, Bus0, MAX_DEVICE
from spread_core.protocols.dali.device import general as device
from spread_core.protocols.dali.exceptions import NoFreeAddress
from spread_core.protocols.dali.gear.events import SCHEME_ADDR_INST_TYPE
from spread_core.tools.settings import logging


class Device2(Device0):
    """Any DALI2 slave device that has been configured with a short address."""

    def __init__(self, address, bus=None, err=False, long=0):
        super(Device2, self).__init__(address, bus, err, long)
        self.instances = dict()

    def __str__(self):
        if len(self.instances) > 0:
            return '; '.join(str(self.instances[tp]) for tp in self.instances)
        return 'unknown device Dali2' + (' ERR' if self.err else '')

    def types(self):
        if self._types is None or len(self._types) == 0:
            self._types = []
            for i in self.instances:
                self._types.append({'type': self.instances[i]._value})
        return self._types


class Bus2(Bus0):
    _dali_type = 2

    def fill_addresses(self):
        if not self._bus_scanned:
            i = self.get_interface()
            for addr in range(0, MAX_DEVICE):
                try:
                    r = i.send(device.QueryNumberOfInstances(Short(addr)))
                    if r and r.value is not None:
                        if r.value.as_integer > 0:
                            if addr not in self._devices:
                                Device2(addr, bus=self)
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
        for sa in l:
            r = i.send(device.QueryNumberOfInstances(Short(sa)))
            if r is not None and r.value is not None:
                inst_num = r.value.as_integer
                if inst_num > 0:
                    if sa not in self._devices:
                        Device2(sa, bus=self)
                    try:
                        result.append(self.init_devices(sa, inst_num, _counter))
                        _counter += 1
                    except BaseException as ex:
                        logging.exception(ex)
            self._on_progress(l.index(sa) + 1)
        self._bus_scanned = True
        return result

    def init_devices(self, sa, inst_num, counter):
        i = self.get_interface()
        addr = Short(sa)
        for instance_num in range(0, inst_num):
            # instance_index = InstanceNumber(instance_num)
            r = i.send(device.QueryInstanceType(addr, InstanceNumber(instance_num)))
            if r and r.value and r.value.as_integer > 0:
                tp = r.value.as_integer
                self._devices[sa].instances[instance_num] = InstanceType(tp)
                i.send(device.DTR0(SCHEME_ADDR_INST_TYPE))
                i.send(device.SetEventScheme(addr, InstanceNumber(instance_num)))
        obj = {
            'address': sa,
            'gtin': self._devices[sa].gtin(i),
            'instances': self._devices[sa].types()
        }
        self._on_found(self.dali_type, obj, counter)
        return obj

    def set_search_addr(self, addr):
        i = self.get_interface()

        h = (addr >> 16) & 0xff
        if self._h != h:
            self._h = h
            i.send(device.SearchAddrH(h))
        m = (addr >> 8) & 0xff

        if self._m != m:
            self._m = m
            i.send(device.SearchAddrM(m))

        l = addr & 0xff
        if self._l != l:
            self._l = l
            i.send(device.SearchAddrL(l))

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
            response = i.send(device.Compare())
            if response.value is True:
                return low
            return None
        time.sleep(0.1)
        response = i.send(device.Compare())
        if response.value is False:
            response = i.send(device.Compare())
        if response.value is True:
            midpoint = (low + high) // 2
            return self.find_next(low, midpoint) \
                or self.find_next(midpoint + 1, high)

    def assign_short_addresses(self, address=0xff, lock_addresses=[]):
        """Search for devices on the bus with no short address allocated, and
        allocate each one a short address from the set of unused
        addresses.
        """
        # if not self._bus_scanned:
        #     self.scan()
        new_devices = []
        addrs = list(self.unused_addresses() - lock_addresses)
        i = self.get_interface()
        i.send(device.Terminate())
        i.send(device.Initialise(address))
        i.send(device.Randomise())
        time.sleep(0.1)
        low = 0
        high = 0xffffff
        while low is not None:
            low = self.find_next(low, high)
            if low is not None:
                if addrs:
                    new_addr = addrs.pop(0)
                    self.set_search_addr(low)
                    i.send(device.ProgramShortAddress(new_addr))
                    r = i.send(device.QueryShortAddress())
                    err = r.value.as_integer != new_addr
                    i.send(device.Withdraw())
                    Device2(new_addr, bus=self, err=err)
                    new_devices.append(new_addr)
                    self._on_progress(len(self._devices))
                else:
                    i.send(device.Terminate())
                    raise NoFreeAddress()
                low = low + 1
        return new_devices

    def find_repetitive_short_addresses(self):
        """Search for devices on the bus with a repetitive short address.
        """
        devices = dict()
        i = self.get_interface()
        i.send(device.Terminate())
        i.send(device.Initialise(0xff))
        i.send(device.Randomise())
        time.sleep(0.1)
        low = 0
        high = 0xffffff
        while low is not None:
            low = self.find_next(low, high)
            if low is not None:
                r = i.send(device.QueryShortAddress())
                i.send(device.Withdraw())
                addr = r.value.as_integer
                if addr not in devices:
                    devices[addr] = []
                devices[addr].append(Device2(addr, long=low))
                self._on_progress(len(devices))
                low = low + 1
        return devices

    def program_short_address(self, long, short):
        self.set_search_addr(long)
        i = self.get_interface()
        if i:
            i.send(device.ProgramShortAddress(short))

    @staticmethod
    def read_memory_location(i, entity_addr, bank_id, start_address, end_address):
        result = b''
        i.send(device.DTR1(bank_id))
        i.send(device.DTR0(start_address))
        for _dtr0 in range(start_address, end_address):
            res = i.send(device.ReadMemoryLocation(entity_addr))
            if res.value:
                result += res.value.pack
            else:
                return result

        return result
