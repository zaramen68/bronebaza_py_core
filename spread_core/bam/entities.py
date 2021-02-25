from spread_core.tools import settings


class Entity:
    _dumped = []

    def __init__(self, _id):
        self._id = _id
        self.values = dict()

    def is_dumped(self, key) -> bool: return key in self._dumped

    @property
    def id(self):
        return self._id

    def __str__(self):
        return '{}({})'.format(self.__class__.__name__, self.id)

    def __repr__(self):
        return self.__str__()

    def get_value(self, funit_type, def_value=None):
        if funit_type in self.values:
            return self.values[funit_type]
        _exist, _ow = settings.get_dump(self.__class__.__name__, self.id, funit_type)
        if _exist:
            return _ow
        if def_value is not None:
            return def_value
        return None

    def set_value(self, key, value):
        self.values[key] = value
        if self.is_dumped(key):
            settings.set_dump(self, key, value)

    def is_value_present(self, key):
        return key in self.values

    def get_address(self, funit_id):
        raise NotImplementedError()
