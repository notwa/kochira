"""
Bad word filtering.

Kick people for using bad words.
"""

import re
import itertools

from peewee import CharField

from kochira import config
from kochira.auth import requires_permission
from kochira.db import Model
from kochira.service import Service, Config

service = Service(__name__, __doc__)

def is_regex(what):
    return what[0] == "/" and what[-1] == "/"


@service.model
class Badword(Model):
    client_name = CharField(255)
    channel = CharField(255)
    word = CharField(255)

    class Meta:
        indexes = (
            (("client_name", "channel", "word"), True),
        )


@service.config
class Config(Config):
    chanserv_kick = config.Field(doc="Ask ChanServ to perform the kick.", default=False)
    chanserv_op = config.Field(doc="Ask ChanServ to op with the given command, if not already opped.", default=None)
    kick_message = config.Field(doc="Kick message.", default="Watch your language!")


@service.command("(?P<word>.+) is a bad word", mention=True)
@requires_permission("badword")
def add_badword(ctx, word):
    """
    Add a bad word.

    Next person to say the bad word will be kicked. Bad word can be delimited
    by forward slashes to act as a regular expression.
    """
    if Badword.select().where(Badword.client_name == ctx.client.name,
                              Badword.channel == ctx.target,
                              Badword.word == word).exists():
        ctx.respond(ctx._("That's already a bad word."))
        return

    Badword.create(client_name=ctx.client.name, channel=ctx.target, word=word).save()

    ctx.respond(ctx._("Okay, whoever says that will be kicked."))


@service.command("(?P<word>.+) is (?:not|no longer) a bad word", mention=True, priority=2550)
@requires_permission("badword")
def remove_badword(ctx, word):
    """
    Remove a bad word.

    Permits the word to be said freely on the channel.
    """
    if Badword.delete().where(Badword.client_name == ctx.client.name,
                              Badword.channel == ctx.target,
                              Badword.word == word).execute() == 0:
        ctx.respond(ctx._("That's not a bad word."))
        return

    ctx.respond(ctx._("Okay, that's not a bad word anymore."))


@service.command("(?:list )?bad words", mention=True)
def list_badwords(ctx):
    """
    List bad words.

    List all bad words enforced.
    """
    ctx.respond(ctx._("The following are bad words: {badwords}").format(
        badwords=", ".join(badword.word if is_regex(badword.word) else "\"" + badword.word + "\""
                           for badword in Badword.select().where(Badword.client_name == ctx.client.name,
                                                                 Badword.channel == ctx.target).order_by(Badword.word))
    ))


@service.hook("channel_message", priority=2500)
def check_badwords(ctx, target, origin, message):
    def _callback():
        if ctx.config.chanserv_kick:
            ctx.client.message("ChanServ", "KICK {target} {origin} {message}".format(
                               target=ctx.target, origin=ctx.origin,
                               message=ctx.config.kick_message))
        else:
            ctx.client.rawmsg("KICK", ctx.target, ctx.origin,
                              ctx.config.kick_message)

    for badword in Badword.select().where(Badword.client_name == ctx.client.name,
                                          Badword.channel == ctx.target):
        if is_regex(badword.word):
            expr = badword.word[1:-1]
        else:
            expr = r"\b{}\b".format(re.escape(badword.word))

        if re.search(expr, message, re.I) is not None:
            op_modes = set(itertools.takewhile(lambda x: x != "v",
                                               ctx.client._nickname_prefixes.values()))

            ops = set([])

            for op_mode in op_modes:
                ops.update(ctx.client.channels[target]["modes"].get(op_mode, []))

            if ctx.client.nickname not in ops and ctx.config.chanserv_op is not None:
                ctx.client.message("ChanServ", ctx.config.chanserv_op.format(
                                   target=ctx.target, me=ctx.client.nickname))
                ctx.bot.event_loop.schedule(_callback)
            else:
                _callback()
            return Service.EAT
