"""
Greet user.

Greet people when they enter the channel.
"""

from kochira.service import Service, coroutine
from kochira.userdata import UserData

service = Service(__name__, __doc__)


@service.command(r"!nogreet$", mention=False)
@coroutine
def forget_greeting(ctx):
    """
    Forget greeting.

    Remove the given greeting text from the user.
    """

    try:
        user_data = yield ctx.lookup_user_data()
    except UserData.DoesNotExist:
        exists = False
    else:
        exists = "greeting" in user_data

    if not exists:
        ctx.respond(ctx._("I don't know who you are."))
        return

    del user_data["greeting"]
    user_data.save()

    ctx.respond(ctx._("Okay, I won't greet you anymore."))


@service.command(r"!setgreet (?P<text>.+)$", mention=False)
@coroutine
def remember_greeting(ctx, text):
    """
    Remember greeting.

    Associate the given greeting text with the user.
    """

    try:
        user_data = yield ctx.lookup_user_data()
    except UserData.DoesNotExist:
        ctx.respond(
            ctx._("Please authenticate with NickServ before you add a greeting."))
        return

    user_data["greeting"] = text
    user_data.save()

    ctx.respond(ctx._("Okay, I'll greet you."))


@service.hook("join")
@coroutine
def greet(ctx, channel, who):
    user_data = yield UserData.lookup_default(ctx.client, who)
    try:
        greeting = user_data["greeting"]
    except KeyError:
        return
    else:
        ctx.message(greeting)
