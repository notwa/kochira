"""
Google Image search.

Find image results
"""

import requests

from kochira.service import Service, background

service = Service(__name__, __doc__)


@service.command(r"!image (?P<term>.+?)(?: (?P<num>\d+))?$")
@service.command(r"image(?: for)? (?P<term>.+?)(?: \((?P<num>\d+)\))?\??$", mention=True)
@background
def image(ctx, term, num: int=None):
    """
    Google.

    Search for the given terms on Google. If a number is given, it will display
    that result.
    """

    r = requests.get(
        "https://ajax.googleapis.com/ajax/services/search/images",
        params={
            "safe": "off",
            "v": "1.0",
            "q": term
        }
    ).json()

    results = r.get("responseData", {}).get("results", [])

    if not results:
        ctx.respond("Couldn't find anything matching \"{term}\".".format(term=term))
        return

    if num is None:
        num = 1

    num -= 1
    total = len(results)

    if num >= total or num < 0:
        ctx.respond("Can't find anything matching \"{term}\".".format(term=term))
        return

    ctx.respond("{url} ({num} of {total})".format(
        url=results[num]["unescapedUrl"],
        num=num + 1,
        total=total
    ))
