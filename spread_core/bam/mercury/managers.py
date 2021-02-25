from spread_core.bam.managers import Manager
from spread_core.mqtt import *


class Mercury(Manager):
    def __init__(self, p_id, m_id):
        super(Mercury, self).__init__(p_id, m_id)

    def parse(self, data):
        super(Mercury, self).parse(data)
        self._bus_id = None
        if 'bus' in data['attributes']:
            self._bus_id = data['attributes']['bus']
            if self.send_interface:
                self.send_interface.set_bus_id(self._bus_id)

    def add_provider(self, data, manager):
        super(Mercury, self).add_provider(data, manager)
        provider = self._providers[data['id']]
        if provider.address not in self._addresses:
            self._addresses[provider.address] = []
        self._addresses[provider.address].append(provider.id)

    def on_ready(self):
        super(Mercury, self).on_ready()
        self.subscribe(TopicTcp(DUMP, self._bus_id))
        self.subscribe(TopicCommand(self.project_id,
                                    entity_addr=ProviderAddress(S_TYPE,
                                                                self._server_id,
                                                                self.__class__.__name__,
                                                                self.id,
                                                                'MercuryElectricMeter',
                                                                '+', '+')))
