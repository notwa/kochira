"""
Google Image search.

Find image results
"""

import requests
from urllib.parse import unquote

from kochira.service import Service, background

service = Service(__name__, __doc__)


@service.command(r"!image (?P<term>.+?)(?: (?P<num>\d+))?$")
@service.command(r"image(?: for)? (?P<term>.+?)(?: \((?P<num>\d+)\))?\??$", mention=True)
@background
def image(client, target, origin, term, num: int=None):
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
        client.message(target, "{origin}: Couldn't find anything matching \"{term}\".".format(
            origin=origin,
            term=term
        ))
        return

    if num is None:
        num = 1

    num -= 1
    total = len(results)

    if num >= total or num < 0:
        client.message(target, "{origin}: Can't find anything matching \"{term}\".".format(
            origin=origin,
            term=term
        ))
        return

    client.message(target, "{origin}: {url} ({num} of {total})".format(
        origin=origin,
        url=results[num]["unescaped_url"],
        num=num + 1,
        total=total
    ))
