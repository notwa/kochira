"""
Choose.

Decide between options.
"""

import binascii
import time

from kochira.service import Service

service = Service(__name__, __doc__)

def _ordering_key(k):
    day = int(time.time() // (60 * 60 * 24))
    return binascii.crc32(k.lower().encode("utf-8"), day)


@service.command(r"choose (?P<options>.+)$", mention=True)
@service.command(r"!choose (?P<options>.+)$")
def choose(ctx, options):
    """
    Choose options.

    Choose options, separated by " or ".
    """

    options = options.split(" or ")
    options.sort(key=_ordering_key)

    ctx.respond(ctx._("I choose: {choice}").format(
        choice=options[-1]
    ))
