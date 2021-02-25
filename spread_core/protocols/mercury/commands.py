import struct

from spread_core.protocols.mercury.errors import PackageError
from spread_core.protocols.mercury.responses import WriteResponse, SerialResponse, DateTimeResponse, \
    DateTimeDaySeasonResponse, \
    StoredEnergyResponse, ValueResponse, ValueResponsePower, LoadStateResponse, VersionResponse, TransformRateResponse, \
    ConnectSuccess


def int2bytes(val):
    if not isinstance(val, int) and not str.isdigit(val):
        raise PackageError('Неверное значение({}). Ожидается значение типа int!'.format(val))
    return int(val).to_bytes(1, 'little')


def crc16(data):
    crc = 0xFFFF
    l = len(data)
    i = 0
    while i < l:
        j = 0
        crc = crc ^ data[i]
        while j < 8:
            if crc & 0x1:
                mask = 0xA001
            else:
                mask = 0x00
            crc = ((crc >> 1) & 0x7FFF) ^ mask
            j += 1
        i += 1
    if crc < 0:
        crc -= 256
    result = crc.to_bytes(2, 'little')
    return result


class MCommand:
    addr_int = None
    _cmd_val = None
    _params = b''
    _pack = None
    _frame_size = 1
    _response = None
    _access_level = 0
    _delimiter = None
    response = None
    _funit_type = None

    def __init__(self, addr):
        if not str.isdigit(str(addr)):
            raise PackageError('Адрес({}) должен быть целым числом!'.format(addr))
        self.addr_int = int(addr)

    def __repr__(self):
        return str(self)

    def __str__(self):
        return '[{}]: {}'.format(self.__class__.__name__, ' '.join(hex(b)[2:].rjust(2, '0') for b in self.pack))

    def set_response(self, data):
        if self._delimiter:
            self.response = self._response(self, data, self.__getattribute__('_delimiter'))
        else:
            self.response = self._response(self, data)

    def is_timed(self):
        return self._access_level > 0

    @property
    def sig(self):
        return None

    @property
    def access_level(self):
        return self._access_level

    @property
    def has_response(self):
        return self._response is not None

    @property
    def pack(self):
        self._pack = self.sign()
        return self._pack

    @property
    def framesize(self):
        return self._frame_size

    def sign(self):
        data = b''
        data += int2bytes(self.addr_int)
        data += int2bytes(self._cmd_val)
        data += struct.pack("B" * len(self._params), *self._params)

        crc = crc16(data)
        return data + crc

    def res_pack(self, funit_type):
        if self._funit_type is not None:
            if isinstance(self.response.value, dict) and funit_type in self.response.value:
                return dict(value=self.response.value[funit_type])
            else:
                return dict(value=self.response.value)

    @property
    def funit_type(self):
        return self._funit_type


class CheckConnect(MCommand):
    _cmd_val = 0x00
    _response = ConnectSuccess


class OpenSession(MCommand):
    _cmd_val = 0x01
    _response = WriteResponse

    def __init__(self, addr, s_type, password):
        super(OpenSession, self).__init__(addr)
        self._params += int2bytes(s_type)
        for sym in password:
            if str.isdigit(sym):
                self._params += int2bytes(sym)
            else:
                self._params += sym.encode('ascii')


class CloseSession(MCommand):
    _cmd_val = 0x02
    _response = WriteResponse


""" 03h """


class WriteCommand(MCommand):
    _cmd_val = 0x03
    _response = WriteResponse
    _access_level = 2


class SetLoad(WriteCommand):
    _params = b'\x31'
    _funit_type = ['SetLoad']

    def __init__(self, addr, state):
        if not str.isdigit(str(state)) or not 0 <= int(state) <= 1:
            raise PackageError('Состояние нагрузки({}) должно быть 1-вкл или 0-выкл!'.format(state))
        state = int(state)
        self.state = state
        self._params += int2bytes(state)
        super(SetLoad, self).__init__(addr)

    def res_pack(self, funit_type):
        return dict(value=(self.state == 1))


class SetTransformRate(WriteCommand):
    ra = None
    rv = None
    _params = b'\x1b'
    _funit_type = ['TransformRateVoltage', 'TransformRateAmperage']

    def __init__(self, addr, TransformRateAmperage, TransformRateVoltage):
        if not str.isdigit(str(TransformRateAmperage)) or not str.isdigit(str(TransformRateVoltage)):
            raise PackageError('Коэффициент трансформации напряжения({}) и тока ({}) должны быть целыми числами!'
                               .format(TransformRateVoltage, TransformRateAmperage))
        TransformRateAmperage = int(TransformRateAmperage)
        TransformRateVoltage = int(TransformRateVoltage)
        self.ra = TransformRateAmperage
        self.rv = TransformRateVoltage
        self._params += struct.pack('>hh', TransformRateVoltage, TransformRateAmperage)
        super(SetTransformRate, self).__init__(addr)

    def res_pack(self, funit_type):
        if funit_type == self._funit_type[0]:
            return dict(value=self.rv)
        else:
            return dict(value=self.ra)


""" 04h """


class OpenCloseTime(MCommand):
    _cmd_val = 0x04
    _params = b'\x12'
    _frame_size = 12
    _response = DateTimeResponse
    _access_level = 1
    _funit_type = ['OpenCloseTime']

    def __init__(self, addr, item_id):
        super(OpenCloseTime, self).__init__(addr)
        if item_id < 0 or item_id > 9:
            raise PackageError('Номер записи({}) должен быть в дипозоне 0..9'.format(item_id))
        self.item_id = item_id
        self._params += int2bytes(item_id)

    def res_pack(self, funit_type):
        return dict(item=self.item_id,
                    value=dict(open=str(self.response.time1).replace(' ', 'T'),
                               close=str(self.response.time2).replace(' ', 'T')))


class CurrentDateTime(MCommand):
    _cmd_val = 0x04
    _params = b'\x00'
    _frame_size = 8
    _access_level = 1
    _response = DateTimeDaySeasonResponse
    _funit_type = ['CurrentDateTime']


""" 05h """


class StoredEnergy(MCommand):
    _cmd_val = 0x05
    _params = b''
    _frame_size = 16
    _access_level = 1
    _delimiter = 1000
    _response = StoredEnergyResponse
    _funit_type = ['StoredEnergyActiveStraight', 'StoredEnergyActiveReverse',
                   'StoredEnergyReactiveStraight', 'StoredEnergyReactiveReverse']

    """ 
        @period разбит на два полубайта: старший полубайт – номер считываемого
        массива, младший полубайт – номер месяца, за который считывается энергия при запросе энер-
        гии за месяц. При запросах не связанных с номером месяца младший полубайт байта не
        имеет значения
            0h - От сброса.
            1h - За текущий год.
            2h - За предыдущий год.
            3h - За месяц.
            4h - За текущие сутки
            5h - За предыдущие сутки
        @tariff:
            0 – энергия по сумме тарифов;
            1 – энергия по тарифу 1;
            2 – энергия по тарифу 2;
            3 - энергия по тарифу 3
            4 - энергия по тарифу 4
        @month: номер месяца, за который считывается энергия при запросе энергии за месяц.
        При запросах не связанных с номером месяца - не имеет значения
        """

    def __init__(self, addr, period, tariff=0, month=1):
        super(StoredEnergy, self).__init__(addr)

        if not isinstance(period, int) and not str.isdigit(str(period)) and int(period) not in range(0, 6):
            raise PackageError('Указатель периода({}) должен быть значением типа int в диапозоне 0..5!'.format(period))

        if not isinstance(tariff, int) and not str.isdigit(str(tariff) and int(period) not in range(0, 5)):
            raise PackageError('Указатель тарифа({}) должен быть значением типа int в диапозоне (0..4)!'.format(tariff))

        if period == 0x3:
            if not str.isdigit(str(month)) or not 1 <= int(month) <= 12:
                raise PackageError('Номер месяца({}) должен быть целым числом в диапозоне 1..12'.format(month))

        period = int(period)
        tariff = int(tariff)
        month = int(month)

        self.period = period
        self.tariff = tariff
        self.month = month
        period = (period << 4) + month

        if not 0 <= tariff <= 4:
            raise PackageError(
                'Номер тарифа({}) должен быть выбран из из диапозона 0..4 (0 - сумма тарифов)'.format(tariff))

        self._params += int2bytes(period)
        self._params += int2bytes(tariff)

    def res_pack(self, funit_type):
        res = super(StoredEnergy, self).res_pack(funit_type)
        res['period'] = self.period
        res['tariff'] = self.tariff
        if self.period == 0x3:
            res['month'] = self.month
        return res


class StoredEnergyCombo(StoredEnergy):
    _funit_type = ['StoredEnergyCombo']


""" 08h """


class SerialCommand(MCommand):
    _cmd_val = 0x08
    _params = b'\x00'
    _frame_size = 7
    _response = SerialResponse
    _funit_type = ['SerialDate']


class TransformRate(MCommand):
    _cmd_val = 8
    _params = b'\x02'
    _frame_size = 4
    _response = TransformRateResponse
    _funit_type = ['TransformRateVoltage', 'TransformRateAmperage']


class Version(MCommand):
    _cmd_val = 8
    _params = b'\x03'
    _frame_size = 3
    _response = VersionResponse
    _funit_type = ['Version']


class Location(MCommand):
    _cmd_val = 0x08
    _params = b'\x0b'
    _frame_size = 4
    _response = VersionResponse
    _funit_type = ['Location']


class AUX(MCommand):
    _cmd_val = 0x08
    _frame_size = 3
    _params = b'\x11'
    _response = ValueResponse
    _access_level = 1
    _min_phase = 1
    _max_phase = 3
    _value_type = None
    _phase = None
    _funit_params = []

    def __init__(self, addr, phase=0):
        super(AUX, self).__init__(addr)
        self._phase = phase - ((phase >> 2) << 2)

        if not isinstance(self._phase, int) or not self._min_phase <= self._phase <= self._max_phase:
            raise PackageError('Номер фазы({}) должен быть в диапозоне {}..{}'
                               .format(self._phase, self._min_phase, self._max_phase))

        self._params += int2bytes((self._value_type << 4) + phase)
        self._funit_params = [self._phase]

    @property
    def phase(self):
        return self._phase

    def res_pack(self, funit_type):
        res = super(AUX, self).res_pack(funit_type)
        res['phase'] = self.phase
        return res


class AUXPower(AUX):
    _value_type = 0
    _delimiter = 100
    _min_phase = 0
    _response = ValueResponsePower
    _funit_type = ['Power']
    
    def __init__(self, addr, power_id, phase):
        if power_id not in range(0, 3):
            raise PackageError('Номер мощности({}) выбирается из диапозона [0-P, 1-Q, 2-S]'.format(power_id))
        super(AUXPower, self).__init__(addr, (power_id << 2) + phase)
        self._power_id = power_id
        self._funit_params.append(power_id)

    def res_pack(self, funit_type):
        res = super(AUXPower, self).res_pack(funit_type)
        res['power_id'] = self._power_id
        return res


class AUXVoltage(AUX):
    _value_type = 1
    _delimiter = 100
    _funit_type = ['Voltage']


class AUXAmperage(AUX):
    _value_type = 2
    _delimiter = 1000
    _funit_type = ['Amperage']


class AUXPowerRate(AUX):
    _value_type = 3
    _delimiter = 1000
    _min_phase = 0
    _response = ValueResponsePower
    _funit_type = ['PowerRate']


class AUXFrequency(AUX):
    _value_type = 4
    _delimiter = 100
    _min_phase = 0
    _funit_type = ['Frequency']


class AUXAngle(AUX):
    _value_type = 5
    _delimiter = 100
    _funit_type = ['Angle']


class AUXTemp(AUX):
    _value_type = 7
    _delimiter = 100
    _frame_size = 2
    _min_phase = 0
    _funit_type = ['Temperature']


class AUXPotentialDifference(AUX):
    _value_type = 8
    _delimiter = 100


class ReadLoadState(MCommand):
    _cmd_val = 8
    _params = b'\x18'
    _frame_size = 2
    _access_level = 1
    _response = LoadStateResponse
