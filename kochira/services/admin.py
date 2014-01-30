import os
import subprocess
import sys

from ..auth import requires_permission
from ..service import Service

service = Service(__name__)

@service.register_command(r"grant (?P<permission>\S+) to (?P<hostmask>\S+)(?: on channel (?P<channel>\S+))?\.?$", mention=True)
@requires_permission("acl")
def grant(client, target, origin, permission, hostmask, channel=None):
    client.grant_permission(hostmask, permission, channel)

    if channel is not None:
        message = "Granted permission \"{permission}\" to {hostmask} on channel {channel} for network \"{network}\".".format(
            permission=permission,
            hostmask=hostmask,
            channel=channel,
            network=client.network
        )
    else:
        message = "Granted permission \"{permission}\" to {hostmask} globally for network \"{network}\".".format(
            permission=permission,
            hostmask=hostmask,
            network=client.network
        )

    client.message(target, message)


@service.register_command(r"revoke (?P<permission>\S+) from (?P<hostmask>\S+)(?: on channel (?P<channel>\S+))?\.?$", mention=True)
@requires_permission("acl")
def revoke(client, target, origin, permission, hostmask, channel=None):
    if permission == "everything":
        permission = None

    client.revoke_permission(hostmask, permission, channel)

    if permission is None:
        message_part = "all permissions"
    else:
        message_part = "permission \"{permission}\"".format(permission=permission)

    if channel is not None:
        message = "Revoked {message_part} from {hostmask} on channel {channel} for network \"{network}\".".format(
            message_part=message_part,
            hostmask=hostmask,
            channel=channel,
            network=client.network
        )
    else:
        message = "Revoked {message_part} from {hostmask} globally for network \"{network}\".".format(
            message_part=message_part,
            hostmask=hostmask,
            network=client.network
        )

    client.message(target, message)


@service.register_command(r"(?P<r>re)?load service (?P<service_name>\S+)$", mention=True)
@requires_permission("services")
def load_service(client, target, origin, r, service_name):
    try:
        client.bot.load_service(service.SERVICES_PACKAGE + '.' + service_name, r is not None)
    except Exception as e:
        client.message(target, "Sorry, couldn't load the service \"{name}\".".format(
            name=service_name
        ))
        client.message(target, "↳ {name}: {info}".format(
            name=e.__class__.__name__,
            info=str(e)
        ))
        return

    if r is not None:
        message = "Reloaded service \"{name}\".".format(name=service_name)
    else:
        message = "Loaded service \"{name}\".".format(name=service_name)

    client.message(target, message)


@service.register_command(r"unload service (?P<service_name>\S+)$", mention=True)
@requires_permission("services")
def unload_service(client, target, origin, service_name):
    try:
        client.bot.unload_service(service.SERVICES_PACKAGE + '.' + service_name)
    except Exception as e:
        client.message(target, "Sorry, couldn't unload the service \"{name}\".".format(
            name=service_name
        ))
        client.message(target, "↳ {name}: {info}".format(
            name=e.__class__.__name__,
            info=str(e)
        ))
        return

    client.message(target, "Unloaded service \"{name}\".".format(name=service_name))


@service.register_command(r"what services are(?: you)? running\??$", mention=True)
@service.register_command(r"(?:list )services$", mention=True)
@requires_permission("services")
def list_services(client, target, origin):
    client.message(target, "I am running: {services}".format(
        services=", ".join(client.bot.services))
    )


@service.register_command(r"eval (?P<code>.+)$", mention=True)
@requires_permission("eval")
def eval_code(client, target, origin, code):
    try:
        result = eval(code, {"client": client}, {})
    except BaseException as e:
        client.message(target, "Sorry, evaluation failed.")
        client.message(target, "↳ {name}: {info}".format(
            name=e.__class__.__name__,
            info=str(e)
        ))
        return

    client.message(target, "Evaluation result: {0!r}".format(result))


@service.register_command(r"rehash$", mention=True)
@requires_permission("rehash")
def rehash(client, target, origin):
    client.bot.rehash()
    client.message(target, "Configuration rehashed.")


@service.register_command(r"re(?:start|boot)$", mention=True)
@requires_permission("restart")
def restart(client, target, origin):
    for client in list(client.bot.networks.values()):
        client.quit("Restarting...")
    os.execvp(os.path.join(sys.path[0], sys.argv[0]), sys.argv)


@service.register_command(r"(?:windows )?update(?:s)?!?", mention=True)
@requires_permission("restart")
def update(client, target, origin):
    client.message(target, "Checking for updates...")

    p = subprocess.Popen(["git", "pull"], stdout=subprocess.PIPE)

    out, _ = p.communicate()

    if p.returncode != 0:
        client.message(target, "Update failed!")
        return

    if out.decode("utf-8").strip() == "Already up-to-date.":
        client.message(target, "No updates.")
        return

    client.message(target, "Update finished!")

    for client in list(client.bot.networks.values()):
        client.quit("Restarting...")
    os.execvp(os.path.join(sys.path[0], sys.argv[0]), sys.argv)
