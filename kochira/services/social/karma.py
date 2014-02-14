"""
Karma tracker.

Enables users to grant each other karma.
"""

from datetime import datetime, timedelta
from peewee import CharField, IntegerField

from kochira import config
from kochira.db import Model
from kochira.service import Service, Config

service = Service(__name__, __doc__)


@service.config
class Config(Config):
    timeout = config.Field(doc="Timeout for granting another user karma, in seconds.", default=30 * 60)


@service.setup
def initialize(bot):
    storage = service.storage_for(bot)

    storage.granters = {}


@service.model
class Karma(Model):
    who = CharField(255)
    network = CharField(255)
    karma = IntegerField()

    class Meta:
        indexes = (
            (("who", "network"), True),
        )


@service.command(r"(?P<who>\S+)\+\+")
def add_karma(client, target, origin, who):
    """
    Add karma.

    Increment a user's karma.
    """
    storage = service.storage_for(client.bot)
    config = service.config_for(client.bot, client.name, target)

    now = datetime.utcnow()

    who_n = client.normalize(who)

    if client.normalize(origin) == who_n:
        client.message(target, "{origin}: You can't give yourself karma.".format(
            origin=origin
        ))
        return

    last_grant = storage.granters.get((origin, client.network),
                                      datetime.fromtimestamp(0))

    if now - last_grant <= timedelta(seconds=config.timeout):
        client.message(target, "{origin}: Please wait a while before granting someone karma.".format(
            origin=origin
        ))
        return

    try:
        karma = Karma.get(Karma.who == who_n, Karma.network == client.network)
    except Karma.DoesNotExist:
        karma = Karma.create(who=who_n, network=client.network, karma=0)

    karma.karma += 1
    karma.save()

    storage.granters[origin, client.network] = now

    client.message(target, "{origin}: {who} now has {n} karma.".format(
        origin=origin,
        who=who,
        n=karma.karma
    ))


@service.command(r"!karma (?P<who>\S+)")
@service.command(r"karma for (?P<who>\S+)", mention=True)
def get_karma(client, target, origin, who):
    """
    Get karma.

    Get the amount of karma for a user.
    """
    who_n = client.normalize(who)

    try:
        karma = Karma.get(Karma.who == who_n, Karma.network == client.network)
    except Karma.DoesNotExist:
        n = 0
    else:
        n = karma.karma

    client.message(target, "{origin}: {who} has {n} karma.".format(
        origin=origin,
        who=who,
        n=n
    ))
