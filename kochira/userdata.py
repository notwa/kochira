import abc
import json
import peewee
import collections
from .db import Model


class JSONField(peewee.Field):
    db_field = "text"

    def db_value(self, value):
        if value is not None:
            value = json.dumps(value)
        return value

    def python_value(self, value):
        if value is not None:
            value = json.loads(value)
        return value


class UserDataMeta(peewee.BaseModel, abc.ABCMeta):
    pass


class UserData(Model, collections.MutableMapping, metaclass=UserDataMeta):
    name = peewee.CharField(255)
    network = peewee.CharField(255)
    data = JSONField()

    class Meta:
        indexes = (
            (("name", "network"), True),
        )

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def __delitem__(self, key):
        del self.data[key]

    def __iter__(self):
        return iter(self.data)

    def __len__(self):
        return len(self.data)

    @classmethod
    def lookup(cls, client, name):
        whois = yield client.whois(name)
        # TODO: the rest of this

    @classmethod
    def _load(cls, name, network):
        try:
            user_data = cls.get(cls.name == name,
                                cls.network == network)
        except cls.DoesNotExist:
            user_data = cls.create(name=name, network=network, data={})
        return user_data

    def __repr__(self):
        return "{__name__}(name={name!r}, network={network!r}, data={data!r})".format(
            __name__=self.__class__.__name__,
            name=self.name, network=self.network, data=self.data
        )
