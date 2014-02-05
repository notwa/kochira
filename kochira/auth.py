import functools

from peewee import CharField, Expression, fn
from .db import Model


def requires_permission(permission):
    def _decorator(f):
        @functools.wraps(f)
        def _inner(client, target, origin, *args, **kwargs):
            hostmask = "{nickname}!{username}@{hostname}".format(
                nickname=origin,
                username=client.users[origin]["username"],
                hostname=client.users[origin]["hostname"]
            )
            if not ACLEntry.has(client.network, hostmask, permission, target):
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

    @classmethod
    def grant(cls, network, hostmask, permission, channel=None):
        """
        Grant a permission to a hostmask.
        """
        if cls.has(hostmask, permission, channel):
            return

        cls.create(hostmask=hostmask, network=network,
                   permission=permission, channel=channel).save()

    @classmethod
    def revoke(cls, network, hostmask, permission, channel=None):
        """
        Revoke a permission from a hostmask.
        """
        ACLEntry.delete().where(Expression(fn.replace(ACLEntry.hostmask, "*", "%"), "ilike", hostmask),
                                ACLEntry.network == network,
                                permission is None or ACLEntry.permission == permission,
                                channel is None or ACLEntry.channel == channel).execute()
