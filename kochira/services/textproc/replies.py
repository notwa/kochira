"""
Automatic replies for keywords.

This service enables the bot to respond to predefined replies specified by
users.
"""

import random
import re
from peewee import CharField
from tornado.web import RequestHandler, Application

from kochira.db import Model

from kochira.service import Service
from kochira.auth import requires_permission

service = Service(__name__, __doc__)


@service.model
class Reply(Model):
    what = CharField(255)
    reply = CharField(255)

    class Meta:
        indexes = (
            (("what",), True),
        )


def is_regex(what):
    return what[0] == "/" and what[-1] == "/"


@service.command(r"stop replying to (?P<what>.+)$", mention=True)
@service.command(r"don't reply to (?P<what>.+)$", mention=True)
@service.command(r"remove reply (?:to|for) (?P<what>.+)$", mention=True)
@requires_permission("reply")
def remove_reply(ctx, what):
    """
    Remove reply.

    Remove the reply for `what`.
    """

    if not Reply.select().where(Reply.what == what).exists():
        ctx.respond(ctx._("I'm not replying to \"{what}\".").format(
            what=what
        ))
        return

    Reply.delete().where(Reply.what == what).execute()

    ctx.respond(ctx._("Okay, I won't reply to {what} anymore.").format(
        what=what if is_regex(what) else "\"" + what + "\""
    ))


@service.hook("channel_message")
def do_reply(ctx, target, origin, message):
    replies = []

    for reply in Reply.select():
        if is_regex(reply.what):
            expr = reply.what[1:-1]
        else:
            expr = r"\b{}\b".format(re.escape(reply.what))
        match = re.search(expr, message, re.I)
        if match is not None:
            replies.append(re.sub(expr, reply.reply, match.group(0), flags=re.I))

    if not replies:
        return

    ctx.message(random.choice(replies))


@service.command(r"reply to (?P<what>.+?) with (?P<reply>.+)$", mention=True)
@requires_permission("reply")
def add_reply(ctx, what, reply):
    """
    Add reply.

    Add an automatic reply for whenever someone says `what`. `what` can be a
    regular expression delimited by ``/``, e.g. ``/^foo$/``.
    """

    if Reply.select().where(Reply.what == what).exists():
        ctx.respond(ctx._("I'm already replying to {what}.").format(
            what=what if is_regex(what) else "\"" + what + "\""
        ))
        return

    Reply.create(what=what, reply=reply).save()

    ctx.respond(ctx._("Okay, I'll reply to {what}.").format(
        what=what if is_regex(what) else "\"" + what + "\""
    ))


@service.command(r"what do you reply to\??$", mention=True)
@service.command(r"replies\??$", mention=True)
def list_replies(ctx):
    """
    List replies.

    List all replies the bot has registered.
    """

    ctx.respond(ctx._("I reply to the following: {replies}").format(
        replies=", ".join(reply.what if is_regex(reply.what) else "\"" + reply.what + "\""
                          for reply in Reply.select().order_by(Reply.what))
    ))


class IndexHandler(RequestHandler):
    def get(self):
        self.render("replies/index.html",
                    replies=Reply.select().order_by(Reply.what))


def make_application(settings):
    return Application([
        (r"/", IndexHandler)
    ], **settings)


@service.hook("services.net.webserver")
def webserver_config(ctx):
    return {
        "name": "replies",
        "title": "Replies",
        "application_factory": make_application
    }
