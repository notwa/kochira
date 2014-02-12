"""
Ignore lists.

This allows the bot to ignore users.
"""

from kochira.db import Model
from peewee import CharField, Expression, fn

from kochira.auth import requires_permission
from kochira.service import Service

service = Service(__name__, __doc__)


class Ignore(Model):
    hostmask = CharField(255)
    network = CharField(255)

    class Meta:
        indexes = (
            (("hostmask", "network"), True),
        )


@service.setup
def initialize_model(bot):
    Ignore.create_table(True)


@service.command(r"(?:ignore|add ignore for) (?P<hostmask>\S+)$", mention=True)
@requires_permission("ignore")
def add_ignore(client, target, origin, hostmask):
    """
    Add ignore.

    Add an ignore for the specified hostmask. Can contain wildcards.
    """

    if Ignore.select().where(Ignore.hostmask == hostmask,
                             Ignore.network == client.name).exists():
        client.message(target, "{origin}: I'm already ignoring {hostmask}.".format(
            origin=origin,
            hostmask=hostmask
        ))
        return

    Ignore.create(hostmask=hostmask, network=client.name).save()

    client.message(target, "{origin}: Okay, now ignoring everything from {hostmask}.".format(
        origin=origin,
        hostmask=hostmask
    ))


@service.command(r"(?:list )?ignores$", mention=True)
@requires_permission("ignore")
def list_ignores(client, target, origin):
    """
    List ignores.

    List all ignores for the bot on the current network.
    """

    client.message(target, "{origin}: Ignores for {network}: {ignores}".format(
        origin=origin,
        network=client.name,
        ignores=", ".join(ignore.hostmask for ignore in
                          Ignore.select().where(Ignore.network == client.name))
    ))


@service.command(r"(?:unignore|don't ignore|stop ignoring|remove ignore from) (?P<hostmask>\S+)$", mention=True)
@requires_permission("ignore")
def remove_ignore(client, target, origin, hostmask):
    """
    Remove ignore.

    Remove an ignore for the specified hostmask. Must match hostmask in ignore list
    exactly.
    """

    if Ignore.delete().where(Ignore.hostmask == hostmask,
                             Ignore.network == client.name).execute() == 0:
        client.message(target, "{origin}: I'm not ignoring {hostmask}.".format(
            origin=origin,
            hostmask=hostmask
        ))
        return

    client.message(target, "{origin}: Okay, stopped ignoring everything from {hostmask}.".format(
        origin=origin,
        hostmask=hostmask
    ))


@service.hook("channel_message", priority=9999)
def ignore_message(client, target, origin, message):
    hostmask = "{nickname}!{username}@{hostname}".format(
        nickname=origin,
        username=client.users[origin]["username"],
        hostname=client.users[origin]["hostname"]
    )

    if Ignore.select().where(Expression(hostmask, "ilike", fn.replace(Ignore.hostmask, "*", "%")),
                             Ignore.network == client.name).exists():
        return service.EAT
