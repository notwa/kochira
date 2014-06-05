"""
UrbanDictionary lookup.

Retrieves definitions of terms from UrbanDictionary.
"""

import requests

from kochira.service import Service, background

service = Service(__name__, __doc__)


@service.command(r"!ud (?P<term>.+?)(?: (?P<num>\d+))?$")
@background
def define(ctx, term, num: int=None):
    """
    Define.

    Look up the given term on UrbanDictionary.
    """

    r = requests.get("http://api.urbandictionary.com/v0/define", params={
        "term": term
    }).json()

    if r["result_type"] != "exact":
        ctx.respond(ctx._("I don't know what \"{term}\" means.").format(term=term))
        return

    if num is None:
        num = 1

    # offset definition
    num -= 1
    total = len(r["list"])

    if num >= total or num < 0:
        ctx.respond(ctx._("Can't find that definition of \"{term}\".").format(term=term))
        return

    ctx.respond(ctx._("{term}: {definition} ({num} of {total})").format(
        term=term,
        definition=r["list"][num]["definition"].replace("\r", "").replace("\n", " "),
        num=num + 1,
        total=total
    ))
