"""
8ball simulator.

It's like a real 8ball, but on the internet.
"""

import binascii
import time

from kochira.service import Service

OPTIONS = [
    lambda ctx: ctx._("It is certain"),
    lambda ctx: ctx._("It is decidedly so"),
    lambda ctx: ctx._("Without a doubt"),
    lambda ctx: ctx._("Yes, definitely"),
    lambda ctx: ctx._("You may rely on it"),
    lambda ctx: ctx._("As I see it, yes"),
    lambda ctx: ctx._("Most likely"),
    lambda ctx: ctx._("Outlook good"),
    lambda ctx: ctx._("Yes"),
    lambda ctx: ctx._("Signs point to yes"),
    lambda ctx: ctx._("Reply hazy, try again"),
    lambda ctx: ctx._("Ask again later"),
    lambda ctx: ctx._("Better not tell you now"),
    lambda ctx: ctx._("Cannot predict now"),
    lambda ctx: ctx._("Concentrate and ask again"),
    lambda ctx: ctx._("Don't count on it"),
    lambda ctx: ctx._("My reply is no"),
    lambda ctx: ctx._("My sources say no"),
    lambda ctx: ctx._("Outlook not so good"),
    lambda ctx: ctx._("Very doubtful")
]

service = Service(__name__, __doc__)

@service.command(r"ask the 8-?ball (?P<question>.+)$", mention=True)
@service.command(r"!8-?ball (?P<question>.+)$")
def ask_8ball(ctx, question):
    """
    8ball.

    If you don't know what an 8ball does just Google it.
    """

    day = int(time.time() // (60 * 60 * 24))
    i = binascii.crc32(question.lower().encode("utf-8"), day)

    ctx.respond(ctx._("The Magic 8-Ball says: {prediction}").format(
        prediction=OPTIONS[i % len(OPTIONS)](ctx)
    ))
