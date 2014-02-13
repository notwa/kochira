"""
Bad word filtering.

Kick people for using bad words.
"""

import re

from peewee import CharField

from kochira.auth import requires_permission
from kochira.db import Model
from kochira.service import Service

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


@service.command("(?P<word>.+) is a bad word", mention=True)
@requires_permission("badword")
def add_badword(client, target, origin, word):
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
    client.message(target, "{origin}: The following are bad words: {badwords}".format(
        origin=origin,
        badwords=", ".join(badword.word if is_regex(badword.word) else "\"" + badword.word + "\""
                           for badword in Badword.select().where(Badword.client_name == client.name,
                                                                 Badword.channel == target).order_by(Badword.word))
    ))


@service.hook("channel_message")
def check_badwords(client, target, origin, message):
    for badword in Badword.select().where(Badword.client_name == client.name,
                                          Badword.channel == target):
        if is_regex(badword.word):
            expr = badword.word[1:-1]
        else:
            expr = r"\b{}\b".format(re.escape(badword.word))

        if re.search(expr, message, re.I) is not None:
            client.rawmsg("KICK", target, origin, "Watch your language!")
            return Service.EAT
