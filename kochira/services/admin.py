from io import StringIO
import os
import subprocess
import sys

from ..auth import requires_permission
from ..service import Service


service = Service(__name__)


@service.setup
def setup_eval_locals(bot, storage):
    storage.eval_locals = {}

@service.command(r"grant (?P<permission>\S+) to (?P<hostmask>\S+)(?: on channel (?P<channel>\S+))?\.?$", mention=True)
@requires_permission("admin")
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


@service.command(r"revoke (?P<permission>\S+) from (?P<hostmask>\S+)(?: on channel (?P<channel>\S+))?\.?$", mention=True)
@requires_permission("admin")
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


@service.command(r"(?P<r>re)?load service (?P<service_name>\S+)$", mention=True)
@requires_permission("admin")
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


@service.command(r"unload service (?P<service_name>\S+)$", mention=True)
@requires_permission("admin")
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


@service.command(r"what services are(?: you)? running\??$", mention=True)
@service.command(r"(?:list )services$", mention=True)
@requires_permission("admin")
def list_services(client, target, origin):
    client.message(target, "I am running: {services}".format(
        services=", ".join(client.bot.services))
    )


@service.command(r">>> (?P<code>.+)$")
@service.command(r"eval (?P<code>.+)$", mention=True)
@requires_permission("admin")
def eval_code(client, target, origin, code):
    storage = service.storage_for(client.bot)

    buf = StringIO()
    sys.stdout = buf

    try:
        eval(compile(code, "<irc>", "single"),
             {"client": client}, storage.eval_locals)
    except BaseException as e:
        client.message(target, "Sorry, evaluation failed.")
        client.message(target, "↳ {name}: {info}".format(
            name=e.__class__.__name__,
            info=str(e)
        ))
        return
    finally:
        sys.stdout = sys.__stdout__

    output = buf.getvalue().rstrip("\n")

    if output:
        for line in output.split("\n"):
            client.message(target, "<<< {}".format(line))
    else:
        client.message(target, "(no result)")


@service.command(r"rehash$", mention=True)
@requires_permission("admin")
def rehash(client, target, origin):
    client.bot.rehash()
    client.message(target, "Configuration rehashed.")


@service.command(r"re(?:start|boot)$", mention=True)
@requires_permission("admin")
def restart(client, target, origin):
    for client in list(client.bot.networks.values()):
        client.quit("Restarting...")
    os.execvp(os.path.join(sys.path[0], sys.argv[0]), sys.argv)


@service.command(r"(?:windows )?update(?:s)?!?$", mention=True)
@requires_permission("admin")
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
