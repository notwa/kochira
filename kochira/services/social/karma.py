"""
Karma tracker.

Enables users to grant each other karma.
"""

from datetime import datetime, timedelta

from pydle.async import blocking

from kochira import config
from kochira.service import Service, Config
from kochira.userdata import UserData

service = Service(__name__, __doc__)


@service.config
class Config(Config):
    timeout = config.Field(doc="Timeout for granting another user karma, in seconds.", default=30 * 60)


@service.setup
def initialize(bot):
    storage = service.storage_for(bot)

    storage.granters = {}


@service.command(r"(?P<who>\S+)\+\+")
@blocking
def add_karma(client, target, origin, who):
    """
    Add karma.

    Increment a user's karma.
    """
    storage = service.storage_for(client.bot)
    config = service.config_for(client.bot, client.name, target)

    now = datetime.utcnow()

    if client.normalize(origin) == client.normalize(who):
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
        user_data = yield UserData.lookup(client, who)
    except UserData.DoesNotExist:
        client.message(target, "{origin}: {who}'s account is not registered.".format(
            origin=origin,
            who=who
        ))
        return

    user_data.setdefault("karma", 0)
    user_data["karma"] += 1

    storage.granters[origin, client.network] = now

    client.message(target, "{origin}: {who} now has {n} karma.".format(
        origin=origin,
        who=who,
        n=user_data["karma"]
    ))


@service.command(r"!karma (?P<who>\S+)")
@service.command(r"karma for (?P<who>\S+)", mention=True)
@blocking
def get_karma(client, target, origin, who):
    """
    Get karma.

    Get the amount of karma for a user.
    """

    user_data = yield UserData.lookup_default(client, who)
    karma = user_data.get("karma", 0)

    client.message(target, "{origin}: {who} has {n} karma.".format(
        origin=origin,
        who=who,
        n=karma
    ))
