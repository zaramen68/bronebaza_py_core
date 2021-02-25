class MError(BaseException):
    def __init__(self, message, **params):
        super().__init__()
        self.message = message
        self.params = params

    def __str__(self):
        res = '[{}]: {}'.format(self.__class__.__name__, self.message)
        if len(self.params) > 0:
            for param in self.params:
                res += '\n      {}: {}'.format(param, self.params[param])
        return res


class WrongCRC16(MError):
    def __init__(self):
        super().__init__('Неверная контрольная сумма ответа!')


class WriteError(MError):
    def __init__(self, byte_code, text):
        super().__init__('Ошибка записи', byte_code=byte_code, text=text)


class BadConnectResponse(MError):
    def __init__(self):
        super().__init__('Ошибка теста канала связи')


class TimeOutError(MError):
    def __init__(self, cmd):
        super().__init__(message='Нет ответа от счётчика. Возможные причины:'
                                 '\n   − не совпал адрес в последовательности запроса с сетевым адресом счётчика;'
                                 '\n   − не совпала контрольная сумма запроса,переданного в канал связи '
                                 'с посчитанной контрольной суммой запроса после принятия его счётчиком;'
                                 '\n   − обращение на запись по адресу 0;'
                                 '\n   − неверное число байт запроса.',
                         pack=str(cmd))


class PackageError(MError):
    def __init__(self, message, **params):
        super(PackageError, self).__init__(message, **params)
