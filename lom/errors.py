class LomError(BaseException):
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


class ParameterError(LomError):
    pass


class UnknownProfile(LomError):
    def __init__(self, id: int):
        super(UnknownProfile, self).__init__(f'Unknown profile id({id})!')
