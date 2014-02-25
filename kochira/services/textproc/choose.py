"""
Choose.

Decide between options.
"""

import binascii
import time

from kochira.service import Service

service = Service(__name__, __doc__)

@service.command(r"choose (?P<options>.+)$", mention=True)
@service.command(r"!choose (?P<options>.+)$")
def choose(ctx, options):
    """
    Choose options.

    Choose options, separated by " or ".
    """

    options = options.split(" or ")

    ctx.respond(ctx._("I choose: {choice}").format(
        choice=options[(binascii.crc32(" or ".join(options).lower().encode("utf-8")) +
                        int(time.time() // (60 * 60 * 24))) % len(options)]
    ))
