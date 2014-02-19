"""
Google web search.

Run queries on Google and return results.
"""

import requests
from html.parser import HTMLParser

from kochira.service import Service, background

service = Service(__name__, __doc__)

html_parser = HTMLParser()


@service.command(r"!g (?P<term>.+?)(?: (?P<num>\d+))?$")
@service.command(r"(?:search|google)(?: for)? (?P<term>.+?)(?: \((?P<num>\d+)\))?\??$", mention=True)
@background
def search(ctx, term, num: int=None):
    """
    Google.

    Search for the given terms on Google. If a number is given, it will display
    that result.
    """

    r = requests.get(
        "https://ajax.googleapis.com/ajax/services/search/web",
        params={
            "v": "1.0",
            "q": term
        }
    ).json()

    results = r.get("responseData", {}).get("results", [])

    if not results:
        ctx.respond(ctx._("Couldn't find anything matching \"{term}\".").format(term=term))
        return

    if num is None:
        num = 1

    num -= 1
    total = len(results)

    if num >= total or num < 0:
        ctx.respond(ctx._("Couldn't find anything matching \"{term}\".").format(term=term))
        return

    ctx.respond(ctx._("{title}: {url} ({num} of {total})").format(
        title=html_parser.unescape(results[num]["titleNoFormatting"]),
        url=results[num]["unescapedUrl"],
        num=num + 1,
        total=total
    ))
