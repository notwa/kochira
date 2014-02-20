import json
import peewee
import collections
from .db import Model, database

from pydle.async import coroutine


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
    def __init__(self, bot, network, account):
        self.bot = bot
        self.network = network
        self.account = account
        self.refresh()

    def refresh(self):
        self._fields = {}
        self._dirty = set([])

        for kv in self._all_kv_pairs_query():
            self._fields[kv.key] = kv.value

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
        return self._fields[key]

    def __setitem__(self, key, value):
        self._fields[key] = value
        self._dirty.add(key)

    def __delitem__(self, key):
        del self._fields[key]
        self._dirty.add(key)

    def __iter__(self):
        return iter(self._fields)

    def __len__(self):
        return len(self._fields)

    def save(self):
        with database.transaction():
            while self._dirty:
                k = self._dirty.pop()

                if k not in self._fields:
                    self._get_kv_pair(k).delete_instance()
                    continue

                v = self._fields[k]

                try:
                    kv = self._get_kv_pair(k)
                except UserDataKVPair.DoesNotExist:
                    kv = self._make_kv_pair(k, v)
                else:
                    kv.value = v
                kv.save()


    class DoesNotExist(Exception): pass

    @classmethod
    @coroutine
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

        return cls(client.bot, client.network, client.normalize(account))

    @classmethod
    @coroutine
    def lookup_default(cls, client, nickname):
        try:
            r = yield cls.lookup(client, nickname)
        except cls.DoesNotExist:
            return cls(client.bot, client.network, client.normalize(nickname))
        else:
            return r

    def __repr__(self):
        return "<{__name__} network={network!r} account={account!r} {data}>".format(
            __name__=self.__class__.__name__,
            network=self.network,
            account=self.account,
            data=dict(self)
        )
