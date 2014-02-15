class Expando(object):
    def __init__(self, *args, **kwargs):
        self.__dict__.update(kwargs)

    def __repr__(self):
        return "{__name__}({items})".format(
            __name__=self.__class__.__name__,
            items=", ".join("{}={!r}".format(k, v)
                            for k, v in self.__dict__.items())
        )
