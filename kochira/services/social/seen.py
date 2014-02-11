"""
Last seen user.

Record when a user was last seen.
"""

import humanize

from datetime import datetime
from peewee import CharField, TextField, DateTimeField

from kochira.db import Model
from kochira.service import Service

service = Service(__name__, __doc__)


class Seen(Model):
    who = CharField(255)
    channel = CharField(255, null=True)
    network = CharField(255)
    ts = DateTimeField()
    event = CharField(255)
    message = TextField(null=True)

    class Meta:
        indexes = (
            (("who", "network"), True),
        )

    def _format_join(self):
        return "joining {}".format(self.channel)

    def _format_kill(self):
        msg = "killing {}".format(self.channel)
        if self.message is not None:
            msg += " ({})".format(self.message)
        return msg

    def _format_killed(self):
        msg = "being killed by {}".format(self.channel)
        if self.message is not None:
            msg += " ({})".format(self.message)
        return msg

    def _format_kick(self):
        msg = "kicking {}".format(self.channel)
        if self.message is not None:
            msg += " ({})".format(self.message)
        return msg

    def _format_kicked(self):
        msg = "being kicked by {}".format(self.channel)
        if self.message is not None:
            msg += " ({})".format(self.message)
        return msg

    def _format_mode_change(self):
        return "setting modes {} on {}".format(self.message, self.channel)

    def _format_channel_message(self):
        return "messaging {} with \"{}\"".format(self.channel, self.message)

    def _format_nick_change(self):
        return "changing their nickname to {}".format(self.message)

    def _format_nick_changed(self):
        return "changing their nickname from {}".format(self.message)

    def _format_channel_notice(self):
        return "noticing {} with \"{}\"".format(self.channel, self.message)

    def _format_part(self):
        msg = "parting {}".format(self.channel)
        if self.message is not None:
            msg += " ({})".format(self.message)
        return msg

    def _format_topic_change(self):
        return "changing the topic for {}".format(self.channel)

    def _format_quit(self):
        msg = "quitting"
        if self.message is not None:
            msg += " ({})".format(self.message)
        return msg

    def _format_ctcp_action(self):
        return "actioning {} with \"{}\"".format(self.channel, self.message)

    def _format_unknown(self):
        return "doing something"

    def format(self):
        return getattr(self, "_format_" + self.event, self._format_unknown)()


@service.setup
def initialize_models(bot):
    Seen.create_table(True)


def update_seen(client, event, who, channel=None, message=None):
    now = datetime.utcnow()

    try:
        seen = Seen.get(Seen.who == who, Seen.network == client.network)
    except Seen.DoesNotExist:
        seen = Seen.create(who=who, channel=channel, network=client.network,
                           ts=now, event=event,
                           message=message)
    else:
        seen.ts = now
        seen.channel = channel
        seen.event = event
        seen.message = message

    seen.save()


@service.hook("join", priority=5000)
def on_join(client, target, origin):
    update_seen(client, "join", origin, target)


@service.hook("kill", priority=5000)
def on_kill(client, target, by, message=None):
    update_seen(client, "kill", by)
    update_seen(client, "killed", target)


@service.hook("kick", priority=5000)
def on_kick(client, channel, target, by, message=None):
    update_seen(client, "kick", by, channel, message)
    update_seen(client, "kicked", target, channel, message)


@service.hook("mode_change", priority=5000)
def on_mode_change(client, channel, modes, by):
    update_seen(client, "mode_change", by, channel, " ".join(modes))


@service.hook("channel_message", priority=5000)
def on_channel_message(client, target, origin, message):
    update_seen(client, "channel_message", origin, target, message)


@service.hook("nick_change", priority=5000)
def on_nick_change(client, old, new):
    update_seen(client, "nick_change", old, None, new)
    update_seen(client, "nick_changed", old, None, new)


@service.hook("channel_notice", priority=5000)
def on_channel_notice(client, target, origin, message):
    update_seen(client, "channel_notice", origin, target, message)


@service.hook("part", priority=5000)
def on_part(client, target, origin, message=None):
    update_seen(client, "part", origin, target, message)


@service.hook("topic_change", priority=5000)
def on_topic_change(client, target, message, by):
    update_seen(client, "topic", by, target, message)


@service.hook("quit", priority=5000)
def on_quit(client, origin, message=None):
    update_seen(client, "quit", origin, None, message)


@service.hook("ctcp_action", priority=5000)
def on_ctcp_action(client, origin, target, message):
    update_seen(client, "ctcp_action", origin, target, message)


@service.command(r".seen (?P<who>\S+)")
@service.command(r"when did you last see (?P<who>\S+)\??", mention=True)
def seen(client, target, origin, who):
    try:
        seen = Seen.get(Seen.who == who, Seen.network == client.network)
    except Seen.DoesNotExist:
        client.message(target, "{origin}: I have never seen {who}.".format(
            origin=origin,
            who=who
        ))
    else:
        client.message(target, "{origin}: I last saw {who} {what} {when}.".format(
            origin=origin,
            who=seen.who,
            what=seen.format(),
            when=humanize.naturaltime(datetime.utcnow() - seen.ts)
        ))
