from spread_core.protocols.dali import command
from spread_core.protocols.dali.device.general import _StandardInstanceCommand


class QueryDeadTime(_StandardInstanceCommand):
    _funit_type = ['DeadTime']
    _inputdev = True
    _response = command.Response
    _opcode = 0x2c


class QueryHoldTime(_StandardInstanceCommand):
    _funit_type = ['HoldTime']
    _inputdev = True
    _response = command.Response
    _opcode = 0x2d


class QueryReportTime(_StandardInstanceCommand):
    _funit_type = ['ReportTime']
    _inputdev = True
    _response = command.Response
    _opcode = 0x2e


class QueryCatching(_StandardInstanceCommand):
    _funit_type = ['Catching']
    _inputdev = True
    _response = command.Response
    _opcode = 0x2f


class CatchHoldTime(_StandardInstanceCommand):
    _inputdev = True
    _opcode = 0x20


class SetHoldTime(_StandardInstanceCommand):
    _inputdev = True
    _opcode = 0x21
    _uses_dtr0 = True
    _sendtwice = True


class SetReportTime(_StandardInstanceCommand):
    _inputdev = True
    _opcode = 0x22
    _uses_dtr0 = True
    _sendtwice = True


class SetDeadTime(_StandardInstanceCommand):
    _inputdev = True
    _opcode = 0x23
    _uses_dtr0 = True
    _sendtwice = True


class CancelHoldTime(_StandardInstanceCommand):
    _inputdev = True
    _opcode = 0x24
