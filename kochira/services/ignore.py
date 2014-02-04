from ..db import Model
from peewee import CharField, Expression, fn

from ..auth import requires_permission
from ..service import Service

service = Service(__name__)


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
    if Ignore.select().where(Ignore.hostmask == hostmask,
                             Ignore.network == client.network).exists():
        client.message(target, "{origin}: I'm already ignoring {hostmask}.".format(
            origin=origin,
            hostmask=hostmask
        ))
        return

    Ignore.create(hostmask=hostmask, network=client.network).save()

    client.message(target, "{origin}: Okay, now ignoring everything from {hostmask}.".format(
        origin=origin,
        hostmask=hostmask
    ))


@service.command(r"(?:unignore|don't ignore|stop ignoring|remove ignore from) (?P<hostmask>\S+)$", mention=True)
@requires_permission("ignore")
def remove_ignore(client, target, origin, hostmask):
    if Ignore.delete().where(Ignore.hostmask == hostmask,
                             Ignore.network == client.network).execute() == 0:
        client.message(target, "{origin}: I'm not ignoring this {hostmask}.".format(
            origin=origin,
            hostmask=hostmask
        ))
        return

    client.message(target, "{origin}: Okay, stopped ignoring everything from {hostmask}.".format(
        origin=origin,
        hostmask=hostmask
    ))


@service.hook("message", priority=9999)
def ignore_message(client, target, origin, message):
    hostmask = "{nickname}!{username}@{hostname}".format(
        nickname=origin,
        username=client.users[origin]["username"],
        hostname=client.users[origin]["hostname"]
    )

    if Ignore.select().where(Expression(hostmask, "ilike", fn.replace(Ignore.hostmask, "*", "%")),
                             Ignore.network == client.network).exists():
        return service.EAT
