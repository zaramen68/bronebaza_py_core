from spread_core.protocols.dali import command
from spread_core.protocols.dali.device.general import _StandardInstanceCommand


class QueryDeadTime(_StandardInstanceCommand):
    _funit_type = ['DeadTime']
    _inputdev = True
    _response = command.Response
    _opcode = 0x3d
    _force_answer = True


class QueryReportTime(_StandardInstanceCommand):
    _funit_type = ['ReportTime']
    _inputdev = True
    _response = command.Response
    _opcode = 0x3e
    _force_answer = True


class QueryHysteresis(_StandardInstanceCommand):
    _funit_type = ['Hysteresis']
    _inputdev = True
    _response = command.Response
    _opcode = 0x3f
    _force_answer = True


class QueryHysteresisMin(_StandardInstanceCommand):
    _funit_type = ['HysteresisMin']
    _inputdev = True
    _response = command.Response
    _opcode = 0x3c
    _force_answer = True


class SetReportTime(_StandardInstanceCommand):
    _inputdev = True
    _opcode = 0x30
    _uses_dtr0 = True
    _sendtwice = True


class SetHysteresis(_StandardInstanceCommand):
    _inputdev = True
    _opcode = 0x31
    _uses_dtr0 = True
    _sendtwice = True


class SetDeadTime(_StandardInstanceCommand):
    _inputdev = True
    _opcode = 0x32
    _uses_dtr0 = True
    _sendtwice = True


class SetHysteresisMin(_StandardInstanceCommand):
    _inputdev = True
    _opcode = 0x33
    _uses_dtr0 = True
    _sendtwice = True
