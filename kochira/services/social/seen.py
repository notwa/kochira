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

    def _format_join(self, ctx, show_channel):
        if not show_channel:
            return ctx._("joining a channel")
        else:
            return ctx._("joining {channel}").format(
                channel=self.channel
            )

    def _format_kill(self, ctx, show_channel):
        if self.message is None:
            return ctx._("killing {target} from the network").format(
                target=self.target
            )
        else:
            return ctx._("killing {target} from the network with reason \"{reason}\"").format(
                target=self.target,
                reason=self.reason
            )

    def _format_killed(self, ctx, show_channel):
        if self.message is None:
            return ctx._("being killed from the network by {target}").format(
                target=self.target
            )
        else:
            return ctx._("being killed from the network by {target} with reason \"{reason}\"").format(
                target=self.target,
                reason=self.reason
            )

    def _format_kick(self, ctx, show_channel):
        if not show_channel:
            return ctx._("kicking from a channel")
        else:
            if self.message is None:
                return ctx._("kicking {target} from {channel}").format(
                    target=self.target,
                    channel=self.channel
                )
            else:
                return ctx._("kicking {target} from {channel} with reason \"{reason}\"").format(
                    target=self.target,
                    channel=self.channel,
                    reason=self.message
                )

    def _format_kicked(self, ctx, show_channel):
        if not show_channel:
            return ctx._("being kicked from a channel")
        else:
            if self.message is None:
                return ctx._("being kicked by {target} from {channel}").format(
                    target=self.target,
                    channel=self.channel
                )
            else:
                return ctx._("being kicked by {target} from {channel} with reason \"{reason}\"").format(
                    target=self.target,
                    channel=self.channel,
                    reason=self.message
                )

    def _format_mode_change(self, ctx, show_channel):
        if not show_channel:
            return ctx._("setting modes")
        else:
            return ctx._("setting modes {modes} on {channel}").format(
                modes=self.message,
                channel=self.channel
            )

    def _format_channel_message(self, ctx, show_channel):
        if not show_channel:
            return ctx._("messaging a channel")
        else:
            return ctx._("telling {channel} \"{message}\"").format(
                channel=self.channel,
                message=self.message
            )

    def _format_nick_change(self, ctx, show_channel):
        return ctx._("changing their nickname to {nickname}").format(
            nickname=self.target
        )

    def _format_nick_changed(self, ctx, show_channel):
        return ctx._("changing their nickname from {nickname}").format(
            self.target
        )

    def _format_channel_notice(self, ctx, show_channel):
        if not show_channel:
            return ctx._("noticing a channel")
        else:
            return ctx._("noticing {channel} \"{message}\"").format(
                channel=self.channel,
                message=self.message
            )

    def _format_part(self, ctx, show_channel):
        if not show_channel:
            return ctx._("parting a channel")
        else:
            if self.message is None:
                return ctx._("parting {channel}").format(channel=self.channel)
            else:
                return ctx._("parting {channel} with reason \"{reason}\"").format(
                    channel=self.channel,
                    reason=self.message
                )

    def _format_topic_change(self, ctx, show_channel):
        if not show_channel:
            return ctx._("changing a topic")
        else:
            return ctx._("changing the topic for {channel} to \"{topic}\"").format(
                channel=self.channel,
                topic=self.message
            )

    def _format_quit(self, ctx, show_channel):
        msg = "quitting the network"
        if self.message is not None:
            msg += " with reason \"{}\"".format(self.message)
        return msg

    def _format_ctcp_action(self, ctx, show_channel):
        if not show_channel:
            return ctx._("actioning a channel")
        else:
            return ctx._("actioning {channel} with \"{message}\"").format(
                channel=self.channel,
                message=self.message
            )

    def _format_unknown(self, ctx, show_channel):
        if show_channel:
            return ctx._("in {channel}").format(channel=self.channel)
        else:
            return ctx._("on this network")

    def format(self, ctx, show_channel):
        return getattr(self, "_format_" + self.event, self._format_unknown)(ctx, show_channel)


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
        ctx.respond(ctx._("I have never seen {who}.").format(
            who=who
        ))
    else:
        show_channel = seen.channel == ctx.target or \
            not "s" in ctx.client.channels.get(seen.channel, {}).get("modes", {"s": True})

        ctx.respond(ctx._("I last saw {who} {when}, {what}.").format(
            who=who,
            what=seen.format(show_channel),
            when=humanize.naturaltime(datetime.utcnow() - seen.ts)
        ))
