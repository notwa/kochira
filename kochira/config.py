def _id(x):
    return x


class Field:
    _sentinel = object()
    _total_creation_order = 0

    def __init__(self, type=_id, doc="(undocumented)", default=_sentinel):
        self.type = type
        self.doc = doc
        self.default = default
        self._creation_order = self._total_creation_order
        self.__class__._total_creation_order += 1

    def unpack(self, value):
        return self.type(value)

    def __get__(self, obj, type=None):
        if obj is None:
            return self

        v = obj._fields.get(self.name, self.default)

        if v is Field._sentinel:
            if hasattr(self.type, "get_default"):
                return self.type.get_default()

            raise AttributeError(self.name)

        return v

    def __set__(self, obj, v):
        obj._fields[self.name] = v


class _ConfigMeta(type):
    def __new__(cls, name, bases, dct):
        newcls = type.__new__(cls, name, bases, dct)

        newcls._field_mappings = {}

        for base in bases:
            if hasattr(base, "_field_mappings"):
                newcls._field_mappings.update(base._field_mappings)

        for k, f in dct.items():
            if not isinstance(f, Field):
                continue
            f.name = k
            newcls._field_mappings[k] = f

        newcls._field_defs = sorted(newcls._field_mappings.values(),
                                    key=lambda f: f._creation_order)

        return newcls


class Config(metaclass=_ConfigMeta):
    def __init__(self, values=None):
        if values is None:
            values = {}

        self._fields = {}
        self._extra = {}

        for k, v in values.items():
            if k not in self._field_mappings:
                self._extra[k] = v
                continue
            self._fields[k] = self._field_mappings[k].unpack(v)

    def __repr__(self):
        return "Config({})".format(
            ", ".join("{}={!r}".format(k, v) for k, v in self._fields.items())
        )

    @classmethod
    def interior_type(cls):
        return cls


class Mapping:
    def __init__(self, type):
        self.type = type

    def __call__(self, m):
        return {k: self.type(v) for k, v in m.items()}

    def interior_type(self):
        if hasattr(self.type, "interior_type"):
            return self.type.interior_type()

        return self.type

    def get_default(self):
        return {}


class Many:
    def __init__(self, type):
        self.type = type

    def __call__(self, xs):
        return [self.type(x) for x in xs]

    def interior_type(self):
        if hasattr(self.type, "interior_type"):
            return self.type.interior_type()

        return self.type

    def get_default(self):
        return []
