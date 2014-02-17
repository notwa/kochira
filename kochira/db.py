from peewee import Proxy, Model

database = Proxy()


class Model(Model):
    class Meta:
        database = database
