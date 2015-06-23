import fnmatch


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


CHECKERS = {
    "a": lambda account, user: user.account == account,
    None: lambda hostmask, user: fnmatch.fnmatch(user.hostmask, hostmask)
}

def has_permission(client, user, permission, target=None):
    for mask, permissions in acl_for(client, target).items():
        if mask[0] == "$":
            matcher = CHECKERS[hostmask[1]]
            mask = mask[3:]
        else:
            matcher = CHECKERS[None]

        if matcher(mask, user) and (permission in permissions or "admin" in permissions):
            return True
    return False


def requires_permission(permission):
    def _decorator(f):
        if not hasattr(f, "permissions"):
            f.permissions = set([])
        f.permissions.add(permission)

        return f
    return _decorator
