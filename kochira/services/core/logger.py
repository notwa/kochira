"""
IRC message logger.

Enables logging of messages to flat files.

Configuration Options
=====================

``log_dir``
  Directory to log to.

Commands
========
None.
"""

from datetime import datetime

from kochira.service import Service
from pathlib import Path

service = Service(__name__, __doc__)


def _is_log_open(storage, network, channel):
    return (network, channel) in storage.handles


def _get_file_handle(storage, network, channel):
    k = (network, channel)

    if k not in storage.handles:
        network_path = storage.path / network

        if not network_path.exists():
            network_path.mkdir(parents=True)

        f = (network_path / (channel + ".log")).open("ab", buffering=0)

        storage.handles[k] = f

    return storage.handles[k]


def _hostmask_for(client, nickname):
    return "{username}@{hostname}".format(**client.users[nickname])


def log(client, channel, what):
    now = datetime.utcnow()

    storage = service.storage_for(client.bot)
    _get_file_handle(storage, client.network, channel).write(("{now} {what}\n".format(
        now=now.isoformat(),
        what=what
    )).encode("utf-8"))


def log_message(client, target, origin, message, format):
    sigil = " "

    if target in client.channels:
        for sigil2, mode in client._nickname_prefixes.items():
            if origin in client.channels[target]["modes"].get(mode, []):
                sigil = sigil2

    log(client, target, format.format(sigil=sigil,
                                      origin=origin,
                                      message=message))


def log_global(client, origin, what):
    for channel, info in client.channels.items():
        if origin in info["users"]:
            log(client, channel, what)

    if _is_log_open(service.storage_for(client.bot), client.network, origin):
        log(client, origin, what)


@service.setup
def setup_logger(bot):
    config = service.config_for(bot)
    storage = service.storage_for(bot)

    storage.handles = {}
    storage.path = Path(config["log_dir"])


@service.shutdown
def shutdown_logger(bot):
    storage = service.storage_for(bot)

    for f in storage.handles.values():
        f.close()


@service.hook("own_message", priority=10000)
def on_own_message(client, target, message):
    on_channel_message(client, target, client.nickname, message)


@service.hook("invite", priority=10000)
def on_invite(client, target, origin):
    log(client, origin, "-!- {origin} [{hostmask}] is inviting you to {channel}".format(
        origin=origin,
        hostmask=_hostmask_for(client, origin),
        channel=target))


@service.hook("join", priority=10000)
def on_join(client, target, origin):
    log(client, target, "--> {origin} [{hostmask}] joined".format(
        origin=origin,
        hostmask=_hostmask_for(client, origin)))


@service.hook("kill", priority=10000)
def on_kill(client, target, by, message=None):
    log_global(client, target, "<== {target} was killed by {by}: {message}".format(
               target=target,
               by=by,
               message=message or ""))


@service.hook("kick", priority=10000)
def on_kick(client, channel, target, by, message=None):
    log(client, channel, "<-- {target} was kicked by {by}: {message}".format(
        target=target,
        by=by,
        message=message or ""))


@service.hook("mode_change", priority=10000)
def on_mode_change(client, channel, modes, by):
    log(client, channel, "-!- {by} set modes: {modes}".format(
        by=by,
        modes=modes))


@service.hook("channel_message", priority=10000)
def on_channel_message(client, target, origin, message):
    log_message(client, target, origin, message, "<{sigil}{origin}> {message}")


@service.hook("private_message", priority=10000)
def on_private_message(client, origin, message):
    on_channel_message(client, origin, origin, message)


@service.hook("nick_change", priority=10000)
def on_nick_change(client, old, new):
    what = "-!- {old} is now known as {new}".format(old=old, new=new)

    log_global(client, new, what)
    log_global(client, old, what)


@service.hook("channel_notice", priority=10000)
def on_channel_notice(client, target, origin, message):
    log_message(client, target, origin, message, "-{sigil}{origin}- {message}")


@service.hook("private_notice", priority=10000)
def on_private_notice(client, origin, message):
    on_channel_notice(client, origin, origin, message)


@service.hook("part", priority=10000)
def on_part(client, target, origin, message=None):
    log(client, target, "<-- {origin} parted: {message}".format(
        origin=origin,
        message=message or ""))


@service.hook("topic_change", priority=10000)
def on_topic_change(client, target, message, by):
    log(client, target, "-!- {by} changed the topic: {message}".format(
        by=by,
        message=message))


@service.hook("quit", priority=10000)
def on_quit(client, origin, message=None):
    log_global(client, origin, "<== {origin} [{hostmask}] quit: {message}".format(
               origin=origin,
               hostmask=_hostmask_for(client, origin),
               message=message or ""))


@service.hook("ctcp", priority=10000)
def on_ctcp(client, origin, target, what):
    command, _, message = what.partition(" ")

    if command.lower() == "action":
        log_message(client, target, origin, message, " * {sigil}{origin} {message}")
