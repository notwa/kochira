"""
Karma tracker.

Enables users to grant each other karma.
"""

from datetime import datetime, timedelta

from kochira import config
from kochira.service import Service, Config, coroutine
from kochira.userdata import UserData

service = Service(__name__, __doc__)


@service.config
class Config(Config):
    timeout = config.Field(doc="Timeout for granting another user karma, in seconds.", default=30 * 60)


@service.setup
def initialize(ctx):
    ctx.storage.granters = {}


@service.command(r"(?P<who>\S+)\+\+")
@coroutine
def add_karma(ctx, who):
    """
    Add karma.

    Increment a user's karma.
    """

    now = datetime.utcnow()

    if ctx.client.normalize(ctx.origin) == ctx.client.normalize(who):
        ctx.respond(ctx._("You can't give yourself karma."))
        return

    last_grant = ctx.storage.granters.get((ctx.origin, ctx.client.network),
                                          datetime.fromtimestamp(0))

    if now - last_grant <= timedelta(seconds=ctx.config.timeout):
        ctx.respond(ctx._("Please wait a while before granting someone karma."))
        return

    try:
        user_data = yield UserData.lookup(ctx.client, who)
    except UserData.DoesNotExist:
        ctx.respond(ctx._("{who}'s account is not registered.").format(
            who=who
        ))
        return

    user_data.setdefault("karma", 0)
    user_data["karma"] += 1
    user_data.save()

    ctx.storage.granters[ctx.origin, ctx.client.network] = now

    ctx.respond(ctx._("{who} now has {n} karma.").format(
        who=who,
        n=user_data["karma"]
    ))


@service.command(r"!karma (?P<who>\S+)")
@service.command(r"karma for (?P<who>\S+)", mention=True)
@coroutine
def get_karma(ctx, who):
    """
    Get karma.

    Get the amount of karma for a user.
    """

    user_data = yield UserData.lookup_default(ctx.client, who)
    karma = user_data.get("karma", 0)

    ctx.respond(ctx._("{who} has {n} karma.").format(
        who=who,
        n=karma
    ))
