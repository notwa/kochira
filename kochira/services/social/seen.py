"""
Last seen user.

Record when a user was last seen.
"""

import humanize

from datetime import datetime
from peewee import CharField, TextField, DateTimeField

from kochira.db import Model
from kochira.service import Service

from pydle.client import UNREGISTERED_NICKNAME

service = Service(__name__, __doc__)


@service.model
class Seen(Model):
    who = CharField(255)
    channel = CharField(255, null=True)
    network = CharField(255)
    ts = DateTimeField()
    event = CharField(255)
    message = TextField(null=True)
    target = TextField(null=True)

    class Meta:
        indexes = (
            (("who", "network"), True),
        )

    def _format_join(self, show_channel):
        return "joining {}".format(self.channel if show_channel else "a channel")

    def _format_kill(self, show_channel):
        msg = "killing {} from the network".format(self.target)
        if self.message is not None:
            msg += " with reason \"{}\"".format(self.message)
        return msg

    def _format_killed(self, show_channel):
        msg = "being killed from the network by {}".format(self.target)
        if self.message is not None:
            msg += " with reason \"{}\"".format(self.message)
        return msg

    def _format_kick(self, show_channel):
        msg = "kicking {} from {}".format(self.target if show_channel else "someone",
                                          self.channel if show_channel else "a channel")
        if show_channel and self.message is not None:
            msg += " with reason \"{}\"".format(self.message)
        return msg

    def _format_kicked(self, show_channel):
        msg = "being kicked by {} from {}".format(self.target if show_channel else "someone",
                                                  self.channel if show_channel else "a channel")
        if show_channel and self.message is not None:
            msg += " with reason \"{}\"".format(self.message)
        return msg

    def _format_mode_change(self, show_channel):
        if not show_channel:
            return "setting modes"
        else:
            return "setting modes {} on {}".format(self.message, self.channel)

    def _format_channel_message(self, show_channel):
        if not show_channel:
            return "messaging a channel"
        else:
            return "telling {} \"{}\"".format(self.channel, self.message)

    def _format_nick_change(self, show_channel):
        return "changing their nickname to {}".format(self.target)

    def _format_nick_changed(self, show_channel):
        return "changing their nickname from {}".format(self.target)

    def _format_channel_notice(self, show_channel):
        if not show_channel:
            return "noticing a channel"
        else:
            return "noticing {} \"{}\"".format(self.channel, self.message)

    def _format_part(self, show_channel):
        msg = "parting {}".format(self.channel if show_channel else "a channel")
        if show_channel and self.message is not None:
            msg += " with reason \"{}\"".format(self.message)
        return msg

    def _format_topic_change(self, show_channel):
        if not show_channel:
            return "changing a topic"
        else:
            return "changing the topic for {} to \"{}\"".format(self.channel,
                                                                self.message)

    def _format_quit(self, show_channel):
        msg = "quitting the network"
        if self.message is not None:
            msg += " with reason \"{}\"".format(self.message)
        return msg

    def _format_ctcp_action(self, show_channel):
        if not show_channel:
            return "actioning a channel"
        else:
            return "actioning {} with \"{}\"".format(self.channel,
                                                     self.message)

    def _format_unknown(self, show_channel):
        if show_channel:
            return "in {}".format(self.channel)
        else:
            return "on this network"

    def format(self, show_channel):
        return getattr(self, "_format_" + self.event, self._format_unknown)(show_channel)


def update_seen(client, event, who, channel=None, message=None, target=None):
    now = datetime.utcnow()
    who = client.normalize(who)

    try:
        seen = Seen.get(Seen.who == who,
                        Seen.network == client.network)
    except Seen.DoesNotExist:
        seen = Seen.create(who=who, channel=channel,
                           network=client.network,
                           ts=now, event=event,
                           message=message, target=target)
    else:
        seen.ts = now
        seen.channel = channel
        seen.event = event
        seen.message = message
        seen.target = target

    seen.save()


@service.hook("join", priority=5000)
def on_join(ctx, target, origin):
    update_seen(ctx.client, "join", origin, target)


@service.hook("kill", priority=5000)
def on_kill(ctx, target, by, message=None):
    update_seen(ctx.client, "kill", target=target)
    update_seen(ctx.client, "killed", target=by)


@service.hook("kick", priority=5000)
def on_kick(ctx, channel, target, by, message=None):
    update_seen(ctx.client, "kick", by, channel, message, target=target)
    update_seen(ctx.client, "kicked", target, channel, message, target=by)


@service.hook("mode_change", priority=5000)
def on_mode_change(ctx, channel, modes, by):
    update_seen(ctx.client, "mode_change", by, channel, " ".join(modes))


@service.hook("channel_message", priority=5000)
def on_channel_message(ctx, target, origin, message):
    update_seen(ctx.client, "channel_message", origin, target, message)


@service.hook("nick_change", priority=5000)
def on_nick_change(ctx, old, new):
    if old == UNREGISTERED_NICKNAME:
        return

    update_seen(ctx.client, "nick_change", old, None, target=new)
    update_seen(ctx.client, "nick_changed", new, None, target=old)


@service.hook("channel_notice", priority=5000)
def on_channel_notice(ctx, target, origin, message):
    update_seen(ctx.client, "channel_notice", origin, target, message)


@service.hook("part", priority=5000)
def on_part(ctx, target, origin, message=None):
    update_seen(ctx.client, "part", origin, target, message)


@service.hook("topic_change", priority=5000)
def on_topic_change(ctx, target, message, by):
    update_seen(ctx.client, "topic", by, target, message)


@service.hook("quit", priority=5000)
def on_quit(ctx, origin, message=None):
    update_seen(ctx.client, "quit", origin, None, message)


@service.hook("ctcp_action", priority=5000)
def on_ctcp_action(ctx, origin, target, message):
    update_seen(ctx.client, "ctcp_action", origin, target, message)


@service.command(r"!seen (?P<who>\S+)")
@service.command(r"have you seen (?P<who>\S+)\??", mention=True)
@service.command(r"when did you last see (?P<who>\S+)\??", mention=True)
def seen(ctx, who):
    """
    Have you seen?

    Check when a user was last seen.
    """
    who_n = ctx.client.normalize(who)

    try:
        seen = Seen.get(Seen.who == who_n, Seen.network == ctx.client.network)
    except Seen.DoesNotExist:
        ctx.respond("I have never seen {who}.".format(
            who=who
        ))
    else:
        show_channel = seen.channel == ctx.target or \
            not "s" in ctx.client.channels.get(seen.channel, {}).get("modes", {"s": True})

        ctx.respond("I last saw {who} {when}, {what}.".format(
            who=who,
            what=seen.format(show_channel),
            when=humanize.naturaltime(datetime.utcnow() - seen.ts)
        ))
