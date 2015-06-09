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


@service.model
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


@service.command(r"who(?:'s| is| are|'re)(?: the loudest|loud)(?: .+)?\??$", mention=True)
def loudest(ctx):
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
        ctx.respond(ctx._("Nobody has shouted yet."))
    else:
        ctx.respond(ctx._("Loudest people: {loudest}.").format(
            loudest=", ".join("{who} from {network} ({count} shout{s})".format(
                who=who,
                network=network,
                count=count,
                s="s" if count != 1 else ""
            ) for who, network, count in loudest)
        ))


@service.command(r"who said that\??$", mention=True)
@service.command(r"what was the context of that\??$", mention=True)
def who_said_that(ctx):
    """
    Who said that?

    Get information for who originally said the last shout.
    """

    shouts = {entry.text.strip(): i
              for i, entry in enumerate(ctx.client.backlogs[ctx.target])
              if is_shout(entry.text) and entry.who == ctx.client.nickname}

    q = list(Shout.select() \
        .where((Shout.message << list(shouts.keys())) if shouts else False))

    if not q:
        ctx.respond(ctx._("Er, nobody said that."))
        return

    q.sort(key=lambda shout: shouts[shout.message])

    ctx.respond(ctx._("{shouts}.").format(
        shouts=", ".join(ctx._("{who} from {network} said \"{what}\"").format(
            who=shout.who,
            network=shout.network,
            what=shout.message
        ) for shout in q)
    ))


@service.command(r"how many shouts\??$", mention=True)
@service.command(r"how many times have people shouted\??", mention=True)
@service.command(r"how many times has (?P<who>\S+) shouted\??", mention=True)
@service.command(r"how loud is (?P<who>\S+)\??", mention=True)
def how_many_shouts(ctx, who=None):
    """
    Number of shouts.

    Get the number of times everyone has shouted or, if `who` is specified, how
    many times `who` has shouted.
    """

    if who is None:
        num = Shout.select().count()
        ctx.respond(ctx.ngettext("People have shouted {num} time.",
                                 "People have shouted {num} times.",
                                 num).format(
            num=num,
            s="s" if num != 1 else ""
        ))
    else:
        num = Shout.select().where(Shout.who == who,
                                   Shout.network == ctx.client.network).count()
        ctx.respond(ctx.ngettext("{who} has shouted {num} time.",
                                 "{who} has shouted {num} times.",
                                 num).format(
            who=who,
            num=num,
            s="s" if num != 1 else ""
        ))


@service.hook("channel_message")
def record_or_play_shout(ctx, target, origin, message):
    message = message.strip()

    if not is_shout(message):
        return

    if not Shout.select().where(Shout.message == message).exists():
        Shout.create(who=ctx.origin, network=ctx.client.network,
                     message=message).save()

    q = Shout.select().where(Shout.message != message) \
        .order_by(fn.Random()) \
        .limit(1)

    if q.exists():
        shout = q[0]
        ctx.message(shout.message)
