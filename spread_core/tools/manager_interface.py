from spread_core.tools.settings import logging


class ManagerOfBroker:
    def __init__(self, mqttc, use_retain=True):
        self.mqttc = mqttc

        # говно-версия
        # self.use_retain = use_retain
        # говно-версия END

    def subscribe(self, topic, log=True):
        self.mqttc.subscribe(str(topic))
        if log:
            logging.info('Subscribed to {}'.format(topic))

    def unsubscribe(self, topic, log=True):
        self.mqttc.unsubscribe(str(topic))
        if log:
            logging.info('Unsubscribe from {}'.format(topic))

    # говно-версия

    def publish(self, topic, data, retain=False):
        logging.debug('{0} [{1}]: '.format("R" if retain else " ", topic).ljust(100, '.') + ' {}'.format(data))
        _data = data if isinstance(data, str) else data.pack()
        self.mqttc.publish(str(topic), _data, retain=retain)

    # def publish(self, topic, data, retain=False):
    #     logging.debug(f'{"R" if self.use_retain and retain else " "} [{topic}]: '.ljust(100, '.') + f' {data}')
    #     _data = data if isinstance(data, str) else data.pack()
    #     self.mqttc.publish(str(topic), _data, retain=self.use_retain and retain)
    #
    # def publish_retain(self, topic, data, retain=False):
    #     logging.debug(f'{"R" if retain else " "} [{topic}]: '.ljust(100, '.') + f' {data}')
    #     _data = data if isinstance(data, str) else data.pack()
    #     self.mqttc.publish(str(topic), _data, retain=retain)
    # говно-версия END
