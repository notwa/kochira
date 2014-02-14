import json
import peewee
import collections
from .db import Model

from pydle.async import blocking


class JSONField(peewee.TextField):
    def db_value(self, value):
        if value:
            value = json.dumps(value)
        return value

    def python_value(self, value):
        if value:
            value = json.loads(value)
        return value


class UserDataKVPair(Model):
    account = peewee.CharField(255)
    network = peewee.CharField(255)
    key = peewee.CharField(255)
    value = JSONField()

    class Meta:
        indexes = (
            (("account", "network", "key"), True),
        )


class UserData(collections.MutableMapping):
    def __init__(self, network, account):
        self.network = network
        self.account = account

    def _all_kv_pairs_query(self):
        return UserDataKVPair.select().where(UserDataKVPair.account == self.account,
                                             UserDataKVPair.network == self.network)

    def _make_kv_pair(self, key, value):
        kv_pair = UserDataKVPair.create(account=self.account,
                                        network=self.network,
                                        key=key, value=value)
        return kv_pair


    def _get_kv_pair(self, key):
        return UserDataKVPair.get(UserDataKVPair.account == self.account,
                                  UserDataKVPair.network == self.network,
                                  UserDataKVPair.key == key)

    def __getitem__(self, key):
        try:
            kv_pair = self._get_kv_pair(key)
        except UserDataKVPair.DoesNotExist:
            raise KeyError(key)
        else:
            return kv_pair.value

    def __setitem__(self, key, value):
        try:
            kv_pair = self._get_kv_pair(key)
        except UserDataKVPair.DoesNotExist:
            kv_pair = self._make_kv_pair(key, value)
        else:
            kv_pair.value = value
        kv_pair.save()

    def __delitem__(self, key):
        try:
            kv_pair = self._get_kv_pair(key)
        except UserDataKVPair.DoesNotExist:
            raise KeyError(key)
        else:
            kv_pair.delete_instance()

    def __iter__(self):
        return (kv_pair.key for kv_pair in self._all_kv_pairs_query())

    def __len__(self):
        return self._all_kv_pairs_query().count()


    class DoesNotExist(Exception): pass

    @classmethod
    @blocking
    def lookup(cls, client, nickname):
        whois = yield client.whois(nickname)

        if whois is None:
            raise cls.DoesNotExist

        account = None

        if whois.get("identified", False):
            account = nickname

        if "account" in whois:
            account = whois["account"]

        if account is None:
            raise cls.DoesNotExist

        return cls(client.network, account)

    @classmethod
    @blocking
    def lookup_default(cls, client, nickname):
        try:
            r = yield cls.lookup(client, nickname)
        except cls.DoesNotExist:
            return cls(client.network, nickname)
        else:
            return r

    def __repr__(self):
        return "{__name__}{data}".format(
            __name__=self.__class__.__name__,
            data=dict(self)
        )
