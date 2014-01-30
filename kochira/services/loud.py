import string

from peewee import TextField, CharField, fn

from ..db import Model

from ..service import Service

service = Service(__name__)


class Shout(Model):
    message = TextField()
    who = CharField(255)


@service.register_setup
def initialize_model(bot, storage):
    Shout.create_table(True)
    storage.last_shout = None


@service.register_command(r"who said that\??$",
                          r"what was the context of that\??$", mention=True)
def who_said_that(client, target, origin):
    storage = service.storage_for(client.bot)

    if storage.last_shout is not None:
        context = "{who} said that.".format(who=storage.last_shout.who)
    else:
        context = "Er, nobody said that."

    client.message(target, "{origin}: {context}".format(
        origin=origin,
        context=context
    ))


@service.register_command(r"how many shouts\??$",
                          r"how many times have people shouted\??", mention=True)
def how_many_shouts(client, target, origin):
    client.message(target, "{origin}: I have {num} shouts.".format(
        origin=origin,
        num=Shout.select().count()
    ))


@service.register_command(r"(?P<message>.+)$")
def record_or_play_shout(client, target, origin, message):
    storage = service.storage_for(client.bot)

    if message.upper() != message or \
       len(message) < 4 or \
       not any(c for c in message if c in string.ascii_uppercase):
        return

    message = message.strip()

    if not Shout.select().where(Shout.message == message).exists():
        Shout.create(who=origin, message=message).save()

    q = Shout.select().where(Shout.message != message) \
        .order_by(fn.Random()) \
        .limit(1)

    if q.exists():
        shout = q[0]
        client.message(target, shout.message)
        storage.last_shout = shout
