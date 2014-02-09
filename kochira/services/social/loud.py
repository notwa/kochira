"""
Record and replay shouts.

This service will record all messages in all caps and select a random message
when somebody speaks in all caps.
"""

import string

from peewee import TextField, CharField, fn, SQL

from kochira.db import Model

from kochira.service import Service

service = Service(__name__, __doc__)


class Shout(Model):
    message = TextField()
    who = CharField(255)
    network = CharField(255)

    class Meta:
        indexes = (
            (("message",), True),
            (("who", "network"), False)
        )


def is_shout(text):
    return text.upper() == text and \
       len(text) >= 4 and \
       any(c for c in text if c in string.ascii_uppercase)

@service.setup
def initialize_model(bot):
    storage = service.storage_for(bot)

    Shout.create_table(True)
    storage.last_shout = None


@service.command(r"who(?:'s| is| are|'re)(?: the loudest|loud)(?: .+)?\??$", mention=True)
def loudest(client, target, origin):
    """
    Loudest users.

    Retrieve the top 5 loudest users.
    """

    loudest = [(shout.who, shout.network, shout.count) for shout in
        Shout.select(Shout.who, Shout.network, fn.sum(1).alias("count"))
            .group_by(Shout.who, Shout.network)
            .order_by(SQL("count DESC"))
            .limit(5)
    ]

    if not loudest:
        client.message(target, "{origin}: Nobody has shouted yet.".format(
            origin=origin
        ))
    else:
        client.message(target, "{origin}: Loudest people: {loudest}.".format(
            origin=origin,
            loudest=", ".join("{who} from {network} ({count} shout{s})".format(
                who=who,
                network=network,
                count=count,
                s="s" if count != 1 else ""
            ) for who, network, count in loudest)
        ))


@service.command(r"who said that\??$", mention=True)
@service.command(r"what was the context of that\??$", mention=True)
def who_said_that(client, target, origin):
    """
    Who said that?

    Get information for who originally said the last shout.
    """

    storage = service.storage_for(client.bot)

    if storage.last_shout is not None:
        context = "{who} said that.".format(who=storage.last_shout.who)
    else:
        context = "Er, nobody said that."

    client.message(target, "{origin}: {context}".format(
        origin=origin,
        context=context
    ))


@service.command(r"how many shouts\??$", mention=True)
@service.command(r"how many times have people shouted\??", mention=True)
@service.command(r"how many times has (?P<who>\S+) shouted\??", mention=True)
@service.command(r"how loud is (?P<who>\S+)\??", mention=True)
def how_many_shouts(client, target, origin, who=None):
    """
    Number of shouts.

    Get the number of times everyone has shouted or, if `who` is specified, how
    many times `who` has shouted.
    """

    if who is None:
        num = Shout.select().count()
        client.message(target, "{origin}: People have shouted {num} time{s}.".format(
            origin=origin,
            num=num,
            s="s" if num != 1 else ""
        ))
    else:
        num = Shout.select().where(Shout.who == who).count()
        client.message(target, "{origin}: {who} has shouted {num} time{s}.".format(
            origin=origin,
            who=who,
            num=num,
            s="s" if num != 1 else ""
        ))


@service.hook("channel_message")
def record_or_play_shout(client, target, origin, message):
    storage = service.storage_for(client.bot)

    message = message.strip()

    if not is_shout(message):
        return

    if not Shout.select().where(Shout.message == message).exists():
        Shout.create(who=origin, network=client.network,
                     message=message).save()

    q = Shout.select().where(Shout.message != message) \
        .order_by(fn.Random()) \
        .limit(1)

    if q.exists():
        shout = q[0]
        client.message(target, shout.message)
        storage.last_shout = shout
