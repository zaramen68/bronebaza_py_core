import threading

from spread_core.bam.dali import *
from spread_core.protocols.dali.gear import general as gear
from spread_core.tools import utils


class Tuner:
    def __init__(self, owner):
        self._owner = owner
        self._cmd = None
        self.timer = None
        self.speed = 0.1

    def set_direction(self, cmd, speed):
        self._cmd = cmd
        self.speed = speed
        self.timer = threading.Timer(self._owner.fadeTime, self.step)
        self.timer.setName('Tuner.step Timer')
        self.timer.start()

    def check_state(self, cmd):
        if self._cmd is None:
            if self.timer:
                if self.timer.is_alive():
                    self.timer.cancel()
                self.timer = None

        if isinstance(cmd, (gear.StepUp, gear.StepDown, gear.OnAndStepUp, gear.StepDownAndOff)):
            # if not self.is_device:
            _c_level = self._owner.get_value(STATE_C_LEVEL_RAW, 0)
            if isinstance(cmd, gear.StepUp):
                _c_level += 1
            elif isinstance(cmd, gear.StepDown):
                _c_level -= 1
            elif isinstance(cmd, gear.OnAndStepUp):
                _c_level = self._owner.get_value(F_MIN_LEVEL_RAW) + 1
            elif isinstance(cmd, gear.StepDownAndOff):
                _c_level = 0

            _p_ids = [self._owner.id]
            if self._owner.is_group:
                _p_ids += self._owner.get_group_members()
            elif self._owner.is_broadcast:
                _p_ids += self._owner.get_broadcast_members()

            # for _p_id in _p_ids:
            #     _provider = self._owner._manager._providers[_p_id]
            #     if isinstance(_provider, self._owner.__class__):
            #         _resp = utils.PublishObject(STATE_C_LEVEL_RAW, _c_level, cmd.sig)
            #         _provider.on_update(STATE_C_LEVEL_RAW, _resp, retain=True)
            _publish_value = utils.PublishObject(STATE_C_LEVEL_RAW, _c_level, None)
            self._owner.publish_value(STATE_C_LEVEL_RAW, _publish_value, retain=True)

            if self.timer is None or not self.timer.is_alive():
                self.timer = threading.Timer(self.speed, self.step)
                self.timer.start()

        elif isinstance(cmd, (gear.DAPC, gear.GoToScene, gear.Off, gear.Up, gear.Down, gear.RecallMaxLevel)):
            if self.timer and self.timer.is_alive():
                self.timer.cancel()

            self.timer = threading.Timer(self._owner.fadeTime, self.step)
            self.timer.start()

    def step(self):
        if self._cmd is not None:
            cmd = self._cmd
            if cmd is not None:
                _c_level = self._owner.get_value(STATE_C_LEVEL_RAW, 0)
                if isinstance(cmd, gear.StepUp):
                    if _c_level == 0:
                        cmd = gear.OnAndStepUp(self._owner.short_addr)
                    elif self._owner.values[STATE_C_LEVEL_RAW] >= self._owner.values[F_MAX_LEVEL_RAW]:
                        return
                elif isinstance(cmd, gear.StepDown) and self._owner.values[STATE_C_LEVEL_RAW] <= self._owner.values[F_MIN_LEVEL_RAW]:
                    return

                self._owner.on_command_prepared(cmd)

    def stop(self):
        self._cmd = None
        self._owner.set_value(F_TUNING, 0)
        if self.timer and self.timer.is_alive():
            self.timer.cancel()
        self.timer = None
