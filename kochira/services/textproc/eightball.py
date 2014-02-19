"""
8ball simulator.

It's like a real 8ball, but on the internet.
"""

import binascii
import time

from kochira.service import Service

OPTIONS = [
    "It is certain",
    "It is decidedly so",
    "Without a doubt",
    "Yes, definitely",
    "You may rely on it",
    "As I see it, yes",
    "Most likely",
    "Outlook good",
    "Yes",
    "Signs point to yes",
    "Reply hazy, try again",
    "Ask again later",
    "Better not tell you now",
    "Cannot predict now",
    "Concentrate and ask again",
    "Don't count on it",
    "My reply is no",
    "My sources say no",
    "Outlook not so good",
    "Very doubtful"
]

service = Service(__name__, __doc__)

@service.command(r"ask the 8-?ball (?P<question>.+)$", mention=True)
@service.command(r"!8-?ball (?P<question>.+)$")
def ask_8ball(ctx, question):
    """
    8ball.

    If you don't know what an 8ball does just Google it.
    """

    ctx.respond("The Magic 8-Ball says: {prediction}".format(
        prediction=OPTIONS[(binascii.crc32(question.lower().encode("utf-8")) +
                           int(time.time() // (60 * 60 * 24))) % len(OPTIONS)]
    ))
