import fnmatch
import functools


def acl_for(client, target=None):
    acl = client.config.acl.copy()

    if target is not None:
        if target in client.config.channels:
            channel_acl = client.config.channels[target].acl
        else:
            channel_acl = {}

        for hostmask, permissions in channel_acl.items():
            acl.setdefault(hostmask, set([])).update(permissions)

    return acl


def has_permission(client, hostmask, permission, target=None):
    for match_hostmask, permissions in acl_for(client, target).items():
        if fnmatch.fnmatch(hostmask, match_hostmask) and \
            permission in permissions or "admin" in permissions:
            return True
    return False


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
            if not has_permission(client, hostmask, permission, target):
                return
            return f(client, target, origin, *args, **kwargs)
        return _inner
    return _decorator
