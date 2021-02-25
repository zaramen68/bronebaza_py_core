class Recipe:
    def __init__(self, _id: int,  _type: str):
        self.id = _id
        self.provider_type = _type
        self._engineries = []

    def __str__(self):
        return '{0}<{1}>: {2}'.format(self.__class__.__name__, self.id, str(self._engineries))

    @property
    def engs(self):
        return self._engineries

    def set_enginery(self, eng):
        self._engineries.append(eng)
