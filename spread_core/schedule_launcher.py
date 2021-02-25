import spread_core.bam.handling.triggers
from spread_core.bam.schedule.scheduler import Scheduler
from spread_core.tools.service_launcher import Launcher
from spread_core.tools.settings import config, CALENDAR

spread_core.bam.handling.triggers.CALENDAR_PATH = config[CALENDAR]
PROJECT_ID = config['PROJECT_ID']


class ScheduleLauncher(Launcher):
    _dumped = False

    def __init__(self):
        self._manager = Scheduler(PROJECT_ID, self.mqttc, self.on_exit)
        super(ScheduleLauncher, self).__init__()

    def on_exit(self, sig=None, frame=None):
        self._manager.on_exit()
        super(ScheduleLauncher, self).on_exit(sig, frame)


def run():
    ScheduleLauncher()


if __name__ == '__main__':
    run()
