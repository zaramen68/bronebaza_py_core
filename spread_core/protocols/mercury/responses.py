import datetime
import struct

from spread_core.protocols.mercury.errors import WrongCRC16, WriteError, BadConnectResponse


class MResponse:
    _addr = None
    _data = None
    _crc16 = None
    value = None

    def __init__(self, cmd, frame, *params):
        self.cmd = cmd
        self._addr = int.from_bytes(frame[:1], 'little')
        self._data = frame[1:-2]
        self._crc16 = frame[-2:]

        from spread_core.protocols.mercury.commands import crc16
        if self._crc16 != crc16(frame[:-2]):
            raise WrongCRC16()

        self.parse(*params)

    def parse(self, *params):
        pass

    def __str__(self):
        return '[{}] {}'.format(self.cmd.__class__.__name__, self.value)


class WriteResponse(MResponse):
    result = None

    def parse(self, *params):
        result = self._data[0]
        self.result = result
        mess = 'Неизвестная ошибка записи'
        if result != 0x0:
            if result == b'\x01':
                mess = 'Недопустимая команда или параметр'
            elif result == b'\x02':
                mess = 'Внутренняя ошибка счётчика'
            elif result == b'\x03':
                mess = 'Недостаточен уровень для удовлетворения запроса'
            elif result == b'\x04':
                mess = 'Внутренние часы счётчика уже корректировались в течение текущих суток'
            elif result == b'\x05':
                mess = 'Не открыт канал связи'
            raise WriteError(result, mess)

    @property
    def success(self):
        return self.result == 0x0

    def __str__(self):
        return '[{}] {}'.format(self.cmd.__class__.__name__, 'OK' if self.result == 0x0 else 'Error {}'.format(self.result))


class ConnectSuccess(MResponse):
    def parse(self, *params):
        if len(self._data) != 1:
            raise BadConnectResponse()

        self.value = self._data[0] == 0x00


class SerialResponse(MResponse):
    _serial = None
    _date = None

    def parse(self, *params):
        self._serial = ' '.join(str(b) for b in self._data[:4])
        self._date = datetime.date(2000+self._data[-1], self._data[-2], self._data[-3])
        self.value = dict(serial=self._serial, date=str(self._date).replace(' ', 'T'))


class DateTimeResponse(MResponse):
    time1 = None
    time2 = None

    def parse(self, *params):
        arr = []
        for ch in self._data[-7::-1]:
            arr.append(int(hex(ch)[2:]))
        if arr[0] != 0:
            arr[0] += 2000
            self.time1 = datetime.datetime(*arr)

        arr = []
        for ch in self._data[-1:-7:-1]:
            arr.append(int(hex(ch)[2:]))
        if arr[0] != 0:
            arr[0] += 2000
            self.time2 = datetime.datetime(*arr)

        self.value = dict(time1=str(self.time1).replace(' ', 'T'), time2=str(self.time2).replace(' ', 'T'))


class DateTimeDaySeasonResponse(MResponse):
    time = None
    weekday = None
    is_winter = None

    def parse(self, *params):
        d = self._data

        self.weekday = int(hex(d[3])[2:])
        self.is_winter = int(hex(d[7])[2:]) == 1
        self.time = datetime.datetime(second=int(hex(d[0])[2:]),
                                      minute=int(hex(d[1])[2:]),
                                      hour=int(hex(d[2])[2:]),
                                      day=int(hex(d[4])[2:]),
                                      month=int(hex(d[5])[2:]),
                                      year=2000 + int(hex(d[6])[2:]))

        self.value = dict(time=str(self.time).replace(' ', 'T'), weekday=self.weekday, dst=self.is_winter)


class StoredEnergyResponse(MResponse):
    nrp = None
    nrm = None
    nap = None
    nam = None

    def parse(self, *params):
        d = self._data
        self.nap = struct.unpack('>i', b'' + d[1::-1]+d[3:1:-1])[0]
        self.nap = 0 if self.nap == -1 else self.nap / params[0]
        self.nam = struct.unpack('>i', b'' + d[5:3:-1]+d[7:5:-1])[0]
        self.nam = 0 if self.nam == -1 else self.nam / params[0]
        self.nrp = struct.unpack('>i', b'' + d[9:7:-1]+d[11:9:-1])[0]
        self.nrp = 0 if self.nrp == -1 else self.nrp / params[0]
        self.nrm = struct.unpack('>i', b'' + d[13:11:-1]+d[15:13:-1])[0]
        self.nrm = 0 if self.nrm == -1 else self.nrm / params[0]

        self.value = dict(StoredEnergyActiveStraight=self.nap,
                          StoredEnergyActiveReverse=self.nam,
                          StoredEnergyReactiveStraight=self.nrp,
                          StoredEnergyReactiveReverse=self.nrm)

    def __str__(self):
        return '[{}] A+: {:.3f} | A-: {:.3f} | R+: {:.3f} | R-: {:.3f}'\
            .format(self.cmd.__class__.__name__, self.nap, self.nam, self.nrp, self.nrm)


class ValueResponse(MResponse):
    def parse(self, *params):
        d = self._data.rjust(3, b'\x00')
        self.value = struct.unpack('>i', b'\x00' + d[0:1] + d[2:] + d[1:2])[0] / params[0]

    def __str__(self):
        return '[{}] phase:{}; value: {}'.format(self.cmd.__class__.__name__, self.cmd.phase, self.value)


class ValueResponsePower(ValueResponse):
    def parse(self, *params):
        self._data = int(bin(self._data[0]).rjust(5, '0')[4:], 2).to_bytes(1, 'little') + self._data[1:]
        super(ValueResponsePower, self).parse(*params)


class LoadStateResponse(MResponse):
    is_on = 0
    is_possible = False
    mode = 0
    excess_power_control = False
    excess_energy_control = False
    is_remote_possible = False
    is_possible_on_tariff_1 = False
    is_possible_on_tariff_2 = False
    is_possible_on_tariff_3 = False
    is_possible_on_tariff_4 = False

    def parse(self, *params):
        b0 = bin(self._data[0])[2:].rjust(8, '0')
        b1 = bin(self._data[1])[2:].rjust(8, '0')

        self.is_on = b1[-2] == '1'
        self.is_possible = b1[-7] == '1'
        self.mode = b0[-1] == '1'
        self.excess_power_control = b0[-2] == '1'
        self.excess_energy_control = b0[-3] == '1'
        self.is_remote_possible = b0[-4] == '1'
        self.is_possible_on_tariff_1 = b0[-5] == '1'
        self.is_possible_on_tariff_2 = b0[-6] == '1'
        self.is_possible_on_tariff_3 = b0[-7] == '1'
        self.is_possible_on_tariff_4 = b0[-8] == '1'

    def __str__(self):
        return '[{}] {} {}'.format(self.cmd.__class__.__name__, bin(self._data[0])[2:], bin(self._data[1])[2:])


class VersionResponse(MResponse):
    def parse(self, *params):
        maj = int(hex(self._data[0])[2:].rjust(2, '0'))
        min = int(hex(self._data[1])[2:].rjust(2, '0'))
        bld = int(hex(self._data[2])[2:].rjust(2, '0'))
        self.value = '{}.{}.{}'.format(maj, min, bld)


class TransformRateResponse(MResponse):
    rv = None
    ra = None

    def parse(self, *params):
        self.rv, self.ra = struct.unpack('>hh', self._data)
        self.value = dict(TransformRateVoltage=self.rv, TransformRateAmperage=self.ra)
