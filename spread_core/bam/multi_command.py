import inspect

from spread_core.protocols.dali.command import CommandSignature


class MultiCommand:
    def __init__(self, funit_type, func, *args, **kwargs):
        self.funit_type = funit_type
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self._sig = CommandSignature()

    def call(self):
        _args_len = len(inspect.signature(self.func).parameters)
        if _args_len == 0:
            self.func()
        else:
            self.func(self._sig, *self.args[:(_args_len - 1)], **self.kwargs)

    def set_signature(self, key, session_id):
        self._sig.set_key(key)
        self._sig.set_session_id(session_id)

    @property
    def session_id(self):
        return self._sig.session_id

    @property
    def key(self):
        return self._sig.key

    def __str__(self):
        return '{}(sig, {})'.format(self.func.__name__, ('{}'*len(self.args)).format(*self.args))

    def __repr__(self):
        return str(self)

