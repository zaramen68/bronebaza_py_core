class PublishObject:
    def __init__(self, funit_type, value, sig, invalid=False):
        self.funit_type = funit_type
        self.value = {funit_type: value}
        self._sig = sig
        self.invalid = invalid

    @property
    def sig(self):
        return self._sig


def get_subclass(cl, separator):
    if separator(cl):
        return cl
    else:
        arr = cl.__subclasses__()
        if len(arr) > 0:
            for scl in arr:
                if separator(scl):
                    return scl
                else:
                    try:
                        res = get_subclass(scl, separator)
                        if res:
                            return res
                    except:
                        continue
        else:
            pass
