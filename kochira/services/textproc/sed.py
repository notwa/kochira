"""
Sed-style find and replacement.

Finds patterns in text and replaces it with other terms.
"""

import re2

from kochira.service import Service

service = Service(__name__, __doc__)


@service.command(r"s([^\w\s])(?P<pattern>(?:\\\1|.*?)*)\1(?P<replacement>(?:\\\1|.*?)*)(?:\1(?P<flags>[gis]*))?", eat=False)
@service.command(r"(?P<who>\S+)[,;:] s([^\w\s])(?P<pattern>(?:\\\2|.*?)*)\2(?P<replacement>(?:\\\2|.*?)*)(?:\2(?P<flags>[gis]*))?", eat=False)
def sed(ctx, pattern, replacement, who=None, flags=None):
    """
    Find and replace.

    Find a regular expression pattern and replace it. Flags supported are `i` for
    case insensitive, `g` for global and `s` for dot-all.
    """

    if flags is None:
        flags = ""

    re_flags = re2.UNICODE

    if "i" in flags:
        re_flags |= re2.IGNORECASE
    if "s" in flags:
        re_flags |= re2.DOTALL

    try:
        expr = re2.compile(pattern, re_flags)
    except:
        ctx.respond(ctx._("Couldn't parse that pattern."))
        return

    for entry in list(ctx.client.backlogs.get(ctx.target, []))[1:]:
        if who is None or entry.who == who:
            match = expr.search(entry.text)

            if match is not None:
                try:
                    msg = expr.sub("\x1f" + replacement + "\x1f", entry.text, count=0 if "g" in flags else 1)
                except:
                    ctx.respond(ctx._("Couldn't parse that pattern."))
                    return

                ctx.message("<{who}> {message}".format(who=entry.who, message=msg))
                break
