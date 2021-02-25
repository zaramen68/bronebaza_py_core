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
        super(ProviderNotPresent, self).__init__(f'{_type}({_id}) is not present')


class StateError(EngineryError):
    pass


class ResponseError(CoreError):
    pass


class ClassifierError(CoreError):
    @classmethod
    def of_funit(cls, funit_type: str, *owner: str):
        return cls(f'{funit_type} отсутствует в classifier -> {" -> ".join(list(owner))}')

    @classmethod
    def of_action(cls, action: str, *owner: str):
        return cls(f'Action {action} отсутствует в classifier -> {" -> ".join(list(owner))}')

    @classmethod
    def no_action_type(cls, action: str, *owner: str):
        return cls(f'Action {action} не содержит типов для classifier -> {" -> ".join(list(owner))}')

    @classmethod
    def action_of_func(cls, func: str, *owner: str):
        return cls(f'Метод {func} не определён в classifier -> {" -> ".join(list(owner))}')


class HandlingError(BaseException):
    pass


class AddressError(BaseException):
    pass


class TopicError(BaseException):
    pass


class InitError(CoreError):
    pass
