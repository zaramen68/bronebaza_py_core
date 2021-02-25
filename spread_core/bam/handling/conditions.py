from spread_core.bam.schedule import const


class Condition:
    def __init__(self, *args, **kwargs):
        self._topic = kwargs[const.TOPIC]
        self._value = kwargs[const.VALUE]

    topic = property(fget=lambda self: self._topic)
    value = property(fget=lambda self: self._value)

    def __str__(self):
        return f'{self._topic} is {self._value}'

    def __repr__(self): return self.__str__()

    def is_proper(self):
        return

    @classmethod
    def of(cls, data):
        return cls(**data)
