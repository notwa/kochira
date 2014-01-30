import re
from peewee import CharField, fn

from ..db import Model

from ..service import Service
from ..auth import requires_permission

service = Service(__name__)

class Reply(Model):
    what = CharField(255)
    reply = CharField(255)

    class Meta:
        indexes = (
            (("what",), True),
        )


@service.setup
def initialize_model(bot, storage):
    Reply.create_table(True)


@service.command(r"stop replying to (?P<what>.+)$", mention=True)
@service.command(r"don't reply to (?P<what>.+)$", mention=True)
@service.command(r"remove reply (?:to|for) (?P<what>.+)$", mention=True)
@requires_permission("reply")
def remove_reply(client, target, origin, what):
    if not Reply.select().where(Reply.what == what).exists():
        client.message(target, "{origin}: I'm not replying to \"{what}\".".format(
            origin=origin,
            what=what
        ))
        return

    Reply.delete().where(Reply.what == what).execute()

    client.message(target, "{origin}: Okay, I won't reply to \"{what}\" anymore.".format(
        origin=origin,
        what=what
    ))


@service.hook("message")
def do_reply(client, target, origin, message):
    replies = Reply.select().where(Reply.what << re.split(r"\W+", message)) \
        .order_by(fn.Random()) \
        .limit(1)

    if not replies.exists():
        return

    client.message(target, replies[0].reply)


@service.command(r"reply to (?P<what>.+) with (?P<reply>.+)$", mention=True)
@requires_permission("reply")
def add_reply(client, target, origin, what, reply):
    if Reply.select().where(Reply.what == what).exists():
        client.message(target, "{origin}: I'm already replying to \"{what}\".".format(
            origin=origin,
            what=what
        ))
        return

    Reply.create(what=what, reply=reply).save()

    client.message(target, "{origin}: Okay, I'll reply to \"{what}\".".format(
        origin=origin,
        what=what
    ))


@service.command(r"what do you reply to\??$", mention=True)
@service.command(r"replies\??$", mention=True)
def list_replies(client, target, origin):
    client.message(target, "{origin}: I reply to the following: {replies}".format(
        origin=origin,
        replies=", ".join(reply.what for reply in Reply.select())
    ))