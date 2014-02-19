"""
Ignore lists.

This allows the bot to ignore users.
"""

from kochira.db import Model
from peewee import CharField, Expression, fn

from kochira.auth import requires_permission
from kochira.service import Service

service = Service(__name__, __doc__)


@service.model
class Ignore(Model):
    hostmask = CharField(255)
    # TODO: requires migration from network to client_name
    network = CharField(255)

    class Meta:
        indexes = (
            (("hostmask", "network"), True),
        )


@service.command(r"(?:ignore|add ignore for) (?P<hostmask>\S+)$", mention=True)
@requires_permission("ignore")
def add_ignore(ctx, hostmask):
    """
    Add ignore.

    Add an ignore for the specified hostmask. Can contain wildcards.
    """

    if Ignore.select().where(Ignore.hostmask == hostmask,
                             Ignore.network == ctx.client.name).exists():
        ctx.respond("I'm already ignoring {hostmask}.".format(
            hostmask=hostmask
        ))
        return

    Ignore.create(hostmask=hostmask, network=ctx.client.name).save()

    ctx.respond("Okay, now ignoring everything from {hostmask}.".format(
        hostmask=hostmask
    ))


@service.command(r"(?:list )?ignores$", mention=True)
@requires_permission("ignore")
def list_ignores(ctx):
    """
    List ignores.

    List all ignores for the bot on the current network.
    """

    ctx.respond("Ignores for {network}: {ignores}".format(
        network=ctx.client.name,
        ignores=", ".join(ignore.hostmask for ignore in
                          Ignore.select().where(Ignore.network == ctx.client.name))
    ))


@service.command(r"(?:unignore|don't ignore|stop ignoring|remove ignore from) (?P<hostmask>\S+)$", mention=True, priority=3000)
@requires_permission("ignore")
def remove_ignore(ctx, hostmask):
    """
    Remove ignore.

    Remove an ignore for the specified hostmask. Must match hostmask in ignore list
    exactly.
    """

    if Ignore.delete().where(Ignore.hostmask == hostmask,
                             Ignore.network == ctx.client.name).execute() == 0:
        ctx.respond("I'm not ignoring {hostmask}.".format(
            hostmask=hostmask
        ))
        return

    ctx.respond("Okay, stopped ignoring everything from {hostmask}.".format(
        hostmask=hostmask
    ))


@service.hook("channel_message", priority=2000)
def ignore_message(ctx, target, origin, message):
    hostmask = "{nickname}!{username}@{hostname}".format(
        nickname=origin,
        username=ctx.client.users[origin]["username"],
        hostname=ctx.client.users[origin]["hostname"]
    )

    if Ignore.select().where(Expression(hostmask, "ilike", fn.replace(Ignore.hostmask, "*", "%")),
                             Ignore.network == ctx.client.name).exists():
        return service.EAT
