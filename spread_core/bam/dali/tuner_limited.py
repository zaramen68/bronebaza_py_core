import threading

from spread_core.bam.dali import *
from spread_core.protocols.dali.gear import general as gear
from spread_core.tools import utils


class TunerLimited:
    def __init__(self, owner):
        self._owner = owner
        self._cmd = None
        self.timer = None
        self.speed = 0.1
        self.count = 0
        self._delay = 0

    def set_direction(self, cmd, speed):
        self._cmd = cmd
        self.speed = speed
        self.count = 0
        self._start_timer(self._owner.fadeTime)

        self.set_tunned_flag_for_not_device(True)

    def check_state(self, cmd):
        if self._cmd is None:
            self._stop_timer()

        elif isinstance(cmd, (gear.StepUp, gear.StepDown, gear.OnAndStepUp, gear.StepDownAndOff)):
            # if not self.is_device:
            _c_level = self._owner.get_value(STATE_C_LEVEL_RAW, 0)
            _diff = 0

            if isinstance(cmd, gear.StepUp):
                _diff = 1
            elif isinstance(cmd, gear.StepDown):
                _diff = -1
            elif isinstance(cmd, gear.OnAndStepUp):
                _c_level = self._owner.get_value(F_MIN_LEVEL_RAW)
                _diff = 1
            elif isinstance(cmd, gear.StepDownAndOff):
                _c_level = 0

            _c_level += _diff

            _p_ids = []
            if self._owner.is_group:
                _p_ids += self._owner.get_group_members()
            elif self._owner.is_broadcast:
                _p_ids += self._owner.get_broadcast_members()

            for _p_id in _p_ids:
                _provider = self._owner._manager._providers[_p_id]
                if _provider.is_valid:
                    if isinstance(_provider, self._owner.__class__):
                        _cv = _provider.get_value(STATE_C_LEVEL_RAW)
                        if _cv != 0:
                            _cv += _diff
                            _cv = max(_provider.get_value(F_MIN_LEVEL_RAW, 1), _cv)
                            _cv = min(_provider.get_value(F_MAX_LEVEL_RAW, 254), _cv)
                            _resp = utils.PublishObject(STATE_C_LEVEL_RAW, _cv, cmd.sig)
                            _provider.on_update(STATE_C_LEVEL_RAW, _resp, retain=True)

            _publish_value = utils.PublishObject(STATE_C_LEVEL_RAW, _c_level, None)
            self._owner.publish_value(STATE_C_LEVEL_RAW, _publish_value, retain=True)

            if self.count < 254:
                if self.timer is None or not self.timer.is_alive():
                    self._start_timer(self.speed, True)
            else:
                self.stop()

        elif isinstance(cmd, (gear.DAPC, gear.GoToScene, gear.Off, gear.Up, gear.Down, gear.RecallMaxLevel)):
            self._start_timer(self._owner.fadeTime)

    def step(self):
        if self._cmd is not None:
            cmd = self._cmd
            if cmd is not None:
                if self._delay > 0:
                    self._start_timer(self._delay)
                    self._delay = 0
                else:
                    _c_level = self._owner.get_value(STATE_C_LEVEL_RAW, 0)
                    if isinstance(cmd, gear.StepUp):
                        if _c_level == 0:
                            cmd = gear.OnAndStepUp(self._owner.short_addr)
                    self._owner.on_command_prepared(cmd)

    def stop(self):
        self._cmd = None
        self._delay = 0
        self._owner.set_value(F_TUNING, 0)
        self._stop_timer()
        self.set_tunned_flag_for_not_device(False)

    def _start_timer(self, delay, incement_count=False):
        self._stop_timer()
        self.timer = threading.Timer(delay, self.step)
        self.timer.setName('TunerLimited.step Timer')
        self.timer.start()
        if incement_count:
            self.count += 1

    def _stop_timer(self):
        if self.timer:
            if self.timer.is_alive():
                self.timer.cancel()
            self.timer = None

    def set_tunned_flag_for_not_device(self, flag):
        _p_ids = []
        if self._owner.is_group:
            _p_ids = self._owner.get_group_members()
        elif self._owner.is_broadcast:
            _p_ids = self._owner.get_broadcast_members()

        for _p_id in _p_ids:
            _provider = self._owner._manager._providers[_p_id]
            if isinstance(_provider, self._owner.__class__):
                _provider.is_unaddress_tunned = flag

    def set_pause(self, delay: float):
        self._delay = delay
