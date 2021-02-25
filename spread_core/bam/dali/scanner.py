from spread_core.bam.dali import F_BUS
from spread_core.mqtt import TopicReply
from spread_core.mqtt.variables import VariableJocket, DATA, VALUE
from spread_core.protocols.dali.bus.bus0 import MAX_DEVICE
from spread_core.protocols.dali.bus.bus1 import Bus1
from spread_core.protocols.dali.bus.bus2 import Bus2
from spread_core.protocols.dali.exceptions import NoFreeAddress

COMMAND = 'command'
PARAMETERS = 'parameters'
SCOPE = 'scope'

INTERSECT = 'intersect'

S_SCAN = 'scan'
S_CONSTRUCT = 'construct'
S_EXTEND = 'extend'
S_RESOLUTION = 'resolution'

DALI1 = 'dali1'
DALI2 = 'dali2'
ALL = 'all'


class DaliScanner:
    def __init__(self, manager, sig, form, dali1=True, dali2=True, intersect=False):
        super(DaliScanner, self).__init__()
        self.manager = manager
        self.sig = sig
        self.form = form
        self.dali1 = dali1
        self.dali2 = dali2
        self.intersect = intersect
        if sig:
            self.reply_topic = TopicReply(manager.project_id, sig.session_id)
        self.target_count = 1 + MAX_DEVICE
        if dali1 is True and dali2 is True:
            self.target_count *= 2
        self._preview_progress = 0

    def start(self):
        result = dict(devices=[], devices2=[])
        bus1 = Bus1(interface=self.manager.send_interface, on_progress=self.on_progress, on_found=self.on_found)
        bus2 = Bus2(interface=self.manager.send_interface, on_progress=self.on_progress, on_found=self.on_found)

        lock_addr_1 = {}.keys()
        lock_addr_2 = {}.keys()

        self.on_progress(0)

        if self.dali1:
            for_scan = None
            if not self.intersect and not self.dali2:
                bus2.fill_addresses()
                lock_addr_2 = bus2.used_addresses()
            if self.form == S_EXTEND:
                bus1.fill_addresses()

            if self.form != S_SCAN:
                if self.form == S_RESOLUTION:
                    for_scan = self.address_resolution(bus1)
                else:
                    for_scan = bus1.assign_short_addresses(broadcast=self.form == S_CONSTRUCT, lock_addresses=lock_addr_2)
            result['devices'] = bus1.scan(for_scan)
            self._preview_progress = MAX_DEVICE
            self.update_info(for_scan, bus1)

        if self.dali2:
            for_scan = None
            if not self.intersect:
                bus1.fill_addresses()
                lock_addr_1 = bus1.used_addresses()
            if self.form == S_EXTEND:
                bus2.fill_addresses()

            if self.form != S_SCAN:
                if self.form == S_RESOLUTION:
                    for_scan = self.address_resolution(bus2)
                else:
                    if self.form == S_EXTEND:
                        addr = 0xff >> 1
                    else:
                        addr = 0xff
                    for_scan = bus2.assign_short_addresses(address=addr, lock_addresses=lock_addr_1)

            result['devices2'] = bus2.scan(for_scan)
            self.update_info(for_scan, bus2)

        self._preview_progress = 0
        return result

    def update_info(self, addresess, bus):
        if addresess:
            for addr in addresess:
                if addr in self.manager._addresses:
                    for _p_id in self.manager._addresses[addr]:
                        if _p_id in self.manager._providers:
                            _provider = self.manager._providers[_p_id]
                            if _provider._dali_type == bus.dali_type_int:
                                if _provider.is_valid:
                                    _provider.get_info()

    def on_progress(self, value):
        self.pubish_progress((self._preview_progress + value) / self.target_count * 100)

    def pubish_progress(self, progress):
        if self.sig:
            funit = self.manager.get_funit(F_BUS)
            jocket = VariableJocket.create_data(self.manager.id, funit['id'], 'progress', progress, self.sig.key)
            self.manager.publish(self.reply_topic, jocket.pack())

    def on_found(self, dali_type, device, count):
        if self.sig:
            data = dict(scope='all' if self.dali1 and self.dali2 else 'dali{}'.format(dali_type), value=device, total=count+1)
            jocket = VariableJocket.create_data(self.manager.id, 31090001, 'found', data, self.sig.key)
            jocket.data[DATA] = jocket.data[DATA].pop(VALUE)
            self.manager.publish(self.reply_topic, jocket.pack())

    @staticmethod
    def address_resolution(bus):
        devices = bus.find_repetitive_short_addresses()
        res = []

        addrs = bus._all_addresses - devices.keys()

        for _addr, _arr in devices.items():
            if len(_arr) > 1:
                res.append(_addr)
                _arr.pop(0)
                for _dev in _arr:
                    if addrs:
                        sa = addrs.pop()
                        bus.program_short_address(_dev.long, sa)
                        res.append(sa)
                    else:
                        raise NoFreeAddress()

        return res
