"""
Sed-style find and replacement.

Finds patterns in text and replaces it with other terms.
"""

import re

from kochira.service import Service

service = Service(__name__, __doc__)


@service.command(r"s(\W{1,2})(?P<pattern>(?:[^\1]|\\1)+)\1(?P<replacement>(?:[^\1]|\\1)+)\1(?P<flags>[gis]*)$", eat=False)
@service.command(r"(?P<who>\S+)[,;:] s(\W{1,2})(?P<pattern>(?:[^\2]|\\2)+)\2(?P<replacement>(?:[^\1]|\\2)+)\2(?P<flags>[gis]*)$", eat=False)
def sed(client, target, origin, pattern, replacement, who=None, flags=None):
    """
    Find and replace.

    Find a regular expression pattern and replace it. Flags supported are `i` for
    case insensitive, `g` for global and `s` for dot-all.
    """

    if flags is None:
        flags = ""

    re_flags = re.UNICODE

    if "i" in flags:
        re_flags |= re.IGNORECASE
    if "s" in flags:
        re_flags |= re.DOTALL

    try:
        expr = re.compile(pattern, re_flags)
    except:
        client.message(target, "{origin}: Couldn't parse that pattern.".format(
            origin=origin
        ))
        return

    for other, message in client.backlogs.get(target, []):
        if who is None or other == who:
            match = expr.search(message)

            if match is not None:
                try:
                    msg = expr.sub("\x1f" + replacement + "\x1f", message, count=0 if "g" in flags else 1)
                except:
                    client.message(target, "{origin}: Couldn't parse that pattern.".format(
                        origin=origin
                    ))
                    return

                client.message(target, "<{who}> {message}".format(who=other, message=msg))
                break
