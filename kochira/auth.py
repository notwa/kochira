import functools

from peewee import CharField, Expression, fn
from .db import Model


def requires_permission(permission):
    def _decorator(f):
        if not hasattr(f, "permissions"):
            f.permissions = set([])
        f.permissions.add(permission)

        @functools.wraps(f)
        def _inner(client, target, origin, *args, **kwargs):
            hostmask = "{nickname}!{username}@{hostname}".format(
                nickname=origin,
                username=client.users[origin]["username"],
                hostname=client.users[origin]["hostname"]
            )
            if not ACLEntry.has(client.name, hostmask, permission, target):
                return
            return f(client, target, origin, *args, **kwargs)
        return _inner
    return _decorator


class ACLEntry(Model):
    """
    An entry in the database for an ACL.
    """

    hostmask = CharField()
    network = CharField()
    permission = CharField()
    channel = CharField(null=True)

    class Meta:
        indexes = (
            (("hostmask", "network", "channel"), False),
            (("hostmask", "network", "channel", "permission"), True)
        )


    @classmethod
    def has(cls, network, hostmask, permission, channel=None):
        """
        Check if a hostmask has a given permission.
        """
        return ACLEntry.select().where(Expression(hostmask, "ilike", fn.replace(ACLEntry.hostmask, "*", "%")),
                                       ACLEntry.network == network,
                                       ACLEntry.permission << [permission, "admin"],
                                       (ACLEntry.channel == channel) |
                                       (ACLEntry.channel >> None)).exists()
