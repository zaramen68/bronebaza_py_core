class InvalidDevice(BaseException):
    def __init__(self, entity, **args):
        self._entity = entity
        self.args = args


class CoreError(BaseException):
    def __init__(self, message, **attributes):
        self.message = message
        self.attributes = attributes

    def __str__(self):
        return self.message + ('\n' + str(self.attributes) if len(self.attributes) > 0 else '')


class ProjectError(CoreError):
    pass


class JocketError(CoreError):
    pass


class EngineryError(CoreError):
    def __init__(self, message, **attributes):
        super(EngineryError, self).__init__('[{}]: '.format(self.__class__.__name__) + message, **attributes)


class CommandError(EngineryError):
    @classmethod
    def of_exec(cls, message):
        return cls(message)


class EngineryNotPresent(EngineryError):
    pass


class ProviderNotPresent(EngineryError):
    def __init__(self, _type, _id):
        super(ProviderNotPresent, self).__init__('{0}({1}) is not present'.format(_type, _id))


class StateError(EngineryError):
    pass


class ResponseError(CoreError):
    pass


class ClassifierError(CoreError):
    @classmethod
    def of_funit(cls, funit_type: str, *owner: str):
        return cls('{0} отсутствует в classifier -> {1}'.format(funit_type, " -> ".join(list(owner))))

    @classmethod
    def of_action(cls, action: str, *owner: str):
        return cls('Action {0} отсутствует в classifier -> {1}'.format(action, " -> ".join(list(owner))))

    @classmethod
    def no_action_type(cls, action: str, *owner: str):
        return cls('Action {0} не содержит типов для classifier -> {1}'.format(action, " -> ".join(list(owner))))

    @classmethod
    def action_of_func(cls, func: str, *owner: str):
        return cls('Метод {0} не определён в classifier -> {1}'.format(func, " -> ".join(list(owner))))


class HandlingError(BaseException):
    pass


class AddressError(BaseException):
    pass


class TopicError(BaseException):
    pass


class InitError(CoreError):
    pass
