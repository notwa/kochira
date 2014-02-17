import threading

from peewee import Proxy, Model, SqliteDatabase

database = Proxy()


class Model(Model):
    class Meta:
        database = database
