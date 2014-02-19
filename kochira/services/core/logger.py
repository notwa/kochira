"""
IRC message logger.

Enables logging of messages to flat files.
"""

import threading
from datetime import datetime

from kochira import config
from kochira.service import Service, Config
from pathlib import Path

service = Service(__name__, __doc__)


@service.config
class Config(Config):
    log_dir = config.Field(doc="Path to the log directory.", default="logs")


def _is_log_open(ctx, channel):
    return (ctx.client.name, channel) in ctx.storage.handles


def _get_file_handle(ctx, channel):
    k = (ctx.client.name, channel)

    if k not in ctx.storage.handles:
        client_name_path = ctx.storage.path / ctx.client.name

        if not client_name_path.exists():
            client_name_path.mkdir(parents=True)

        path = client_name_path / (channel + ".log")
        f = path.open("ab")

        service.logger.debug("Opened handle for: %s", path)

        ctx.storage.handles[k] = f

    return ctx.storage.handles[k]


def _hostmask_for(client, nickname):
    user = client.users.get(nickname, {})

    username = user.get("username") or ""
    hostname = user.get("hostname") or ""

    if not username and not hostname:
        return ""

    return "{username}@{hostname}".format(username=username,
                                          hostname=hostname)


def log(ctx, channel, what):
    now = datetime.utcnow()

    f = _get_file_handle(ctx, channel)

    with ctx.storage.lock:
        f.write(("{now} {what}\n".format(
            now=now.isoformat(),
            what=what
        )).encode("utf-8"))
        f.flush()


def log_message(ctx, target, origin, message, format):
    sigil = " "

    if target in ctx.client.channels:
        for sigil2, mode in ctx.client._nickname_prefixes.items():
            if origin in ctx.client.channels[target]["modes"].get(mode, []):
                sigil = sigil2

    log(ctx, target, format.format(sigil=sigil, origin=origin,
                                   message=message))


def log_global(ctx, origin, what):
    for channel, info in ctx.client.channels.items():
        if origin in info["users"]:
            log(ctx, channel, what)

    if _is_log_open(ctx, origin):
        log(ctx, origin, what)


def close_all_handles(storage):
    with storage.lock:
        for f in storage.handles.values():
            f.close()
        storage.handles = {}
    service.logger.debug("Log handles closed")


@service.setup
def setup_logger(ctx):
    ctx.storage.handles = {}
    ctx.storage.path = Path(ctx.config.log_dir)
    ctx.storage.lock = threading.Lock()


@service.shutdown
def shutdown_logger(ctx):
    close_all_handles(ctx.storage)


@service.hook("sighup")
def flush_log_handles(ctx):
    close_all_handles(ctx.storage)


@service.hook("own_message", priority=10000)
def on_own_message(ctx, target, message):
    on_channel_message(ctx, target, ctx.client.nickname, message)


@service.hook("own_notice", priority=10000)
def on_own_notice(ctx, target, message):
    on_channel_notice(ctx, target, ctx.client.nickname, message)


@service.hook("invite", priority=10000)
def on_invite(ctx, target, origin):
    log(ctx, origin, "-!- {origin} [{hostmask}] is inviting you to {channel}".format(
        origin=origin,
        hostmask=_hostmask_for(ctx.client, origin),
        channel=target))


@service.hook("join", priority=10000)
def on_join(ctx, target, origin):
    log(ctx, target, "--> {origin} [{hostmask}] joined".format(
        origin=origin,
        hostmask=_hostmask_for(ctx.client, origin)))


@service.hook("kill", priority=10000)
def on_kill(ctx, target, by, message=None):
    log_global(ctx, target, "<== {target} was killed by {by}: {message}".format(
               target=target,
               by=by,
               message=message or ""))


@service.hook("kick", priority=10000)
def on_kick(ctx, channel, target, by, message=None):
    log(ctx, channel, "<-- {target} was kicked by {by}: {message}".format(
        target=target,
        by=by,
        message=message or ""))


@service.hook("mode_change", priority=10000)
def on_mode_change(ctx, channel, modes, by):
    log(ctx, channel, "-!- {by} set modes: {modes}".format(
        by=by,
        modes=" ".join(modes)))


@service.hook("channel_message", priority=10000)
def on_channel_message(ctx, target, origin, message):
    log_message(ctx, target, origin, message, "<{sigil}{origin}> {message}")


@service.hook("private_message", priority=10000)
def on_private_message(ctx, origin, message):
    on_channel_message(ctx, origin, origin, message)


@service.hook("nick_change", priority=10000)
def on_nick_change(ctx, old, new):
    what = "-!- {old} is now known as {new}".format(old=old, new=new)

    log_global(ctx, new, what)
    log_global(ctx, old, what)


@service.hook("channel_notice", priority=10000)
def on_channel_notice(ctx, target, origin, message):
    log_message(ctx, target, origin, message, "-{sigil}{origin}- {message}")


@service.hook("private_notice", priority=10000)
def on_private_notice(ctx, origin, message):
    on_channel_notice(ctx, origin, origin, message)


@service.hook("part", priority=10000)
def on_part(ctx, target, origin, message=None):
    log(ctx, target, "<-- {origin} parted: {message}".format(
        origin=origin,
        message=message or ""))


@service.hook("topic_change", priority=10000)
def on_topic_change(ctx, target, message, by):
    log(ctx, target, "-!- {by} changed the topic: {message}".format(
        by=by,
        message=message))


@service.hook("quit", priority=10000)
def on_quit(ctx, origin, message=None):
    log_global(ctx, origin, "<== {origin} [{hostmask}] quit: {message}".format(
               origin=origin,
               hostmask=_hostmask_for(ctx.client, origin),
               message=message or ""))


@service.hook("ctcp_action", priority=10000)
def on_ctcp_action(ctx, origin, target, message):
    if target == ctx.client.nickname:
        target = origin

    log_message(ctx, target, origin, message, " * {sigil}{origin} {message}")
