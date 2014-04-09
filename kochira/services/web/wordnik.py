"""
Wordnik lookup.

Retrieves definitions of terms from Wordnik.
"""

import requests

from urllib.parse import quote_plus
from kochira.service import Service, background

service = Service(__name__, __doc__)


@service.command(r"!define (?P<term>.+?)(?: (?P<num>\d+))?$")
@service.command(r"define (?P<term>.+?)(?: \((?P<num>\d+)\))?\??$", mention=True)
@service.command(r"what does (?P<term>.+) mean(?: \((?P<num>\d+)\))?\??$", mention=True)
@background
def define(ctx, term, num: int=None):
    """
    Define.

    Look up the given term on Wordnik.
    """

    r = requests.get("http://api.wordnik.com/v4/word.json/{word}/definitions".format(
        word=quote_plus(term)
    ), params={
        "api_key": ctx.config.api_key
    }).json()

    if not r:
        ctx.respond(ctx._("I don't know what \"{term}\" means.").format(term=term))
        return

    if num is None:
        num = 1

    # offset definition
    num -= 1
    total = len(r)

    if num >= total or num < 0:
        ctx.respond(ctx._("Can't find that definition of \"{term}\".").format(term=term))
        return

    ctx.respond(ctx._("{term}: {definition} ({num} of {total})").format(
        term=r[num]["word"],
        definition=r[num]["text"].replace("\r", "").replace("\n", " "),
        num=num + 1,
        total=total
    ))
