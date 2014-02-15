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
def add_badword(client, target, origin, word):
    """
    Add a bad word.

    Next person to say the bad word will be kicked. Bad word can be delimited
    by forward slashes to act as a regular expression.
    """
    if Badword.select().where(Badword.client_name == client.name,
                              Badword.channel == target,
                              Badword.word == word).exists():
        client.message(target, "{origin}: That's already a bad word.".format(
            origin=origin
        ))
        return

    Badword.create(client_name=client.name, channel=target, word=word).save()

    client.message(target, "{origin}: Okay, next person to say that gets kicked.".format(
            origin=origin
        ))


@service.command("(?P<word>.+) is not a bad word", mention=True, priority=1)
@requires_permission("badword")
def remove_badword(client, target, origin, word):
    """
    Remove a bad word.

    Permits the word to be said freely on the channel.
    """
    if Badword.delete().where(Badword.client_name == client.name,
                              Badword.channel == target,
                              Badword.word == word).execute() == 0:
        client.message(target, "{origin}: That's not a bad word.".format(
            origin=origin
        ))
    else:
        client.message(target, "{origin}: Okay, that's not a bad word anymore.".format(
            origin=origin
        ))


@service.command("(?:list )?bad words", mention=True)
def list_badwords(client, target, origin):
    """
    List bad words.

    List all bad words enforced.
    """
    client.message(target, "{origin}: The following are bad words: {badwords}".format(
        origin=origin,
        badwords=", ".join(badword.word if is_regex(badword.word) else "\"" + badword.word + "\""
                           for badword in Badword.select().where(Badword.client_name == client.name,
                                                                 Badword.channel == target).order_by(Badword.word))
    ))


@service.hook("channel_message", priority=1)
def check_badwords(client, target, origin, message):
    config = service.config_for(client.bot, client.name, target)

    def _callback():
        if config.chanserv_kick:
            client.message("ChanServ", "KICK {target} {origin} {message}".format(
                target=target, origin=origin, message=config.kick_message))
        else:
            client.rawmsg("KICK", target, origin, config.kick_message)

    for badword in Badword.select().where(Badword.client_name == client.name,
                                          Badword.channel == target):
        if is_regex(badword.word):
            expr = badword.word[1:-1]
        else:
            expr = r"\b{}\b".format(re.escape(badword.word))

        if re.search(expr, message, re.I) is not None:
            op_modes = set(itertools.takewhile(lambda x: x != "v",
                                               client._nickname_prefixes.values()))

            ops = set([])

            for op_mode in op_modes:
                ops.update(client.channels[target]["modes"].get(op_mode, []))

            if client.nickname not in ops and config.chanserv_op is not None:
                client.message("ChanServ", config.chanserv_op.format(
                    target=target, me=client.nickname))
                client.bot.event_loop.schedule(_callback)
            else:
                _callback()
            return Service.EAT
