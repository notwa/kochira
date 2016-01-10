"""
Google web search.

Run queries on Google and return results.
"""

import requests

from kochira import config
from kochira.service import Service, background, Config, coroutine
from kochira.userdata import UserData

import kochira.timeout as timeout

service = Service(__name__, __doc__)


@service.config
class Config(Config):
    api_key = config.Field(doc="Google API key.")
    cx = config.Field(doc="Custom search engine ID.")
    safesearch = config.Field(doc="Set safety level.", default="medium")
    # FIXME: this appears to do jack shit
    timeout_messages, timeout_seconds, timeout_global = \
      timeout.config(config.Field, messages=100, seconds=60*60*8, globally=True)


@service.setup
def setup(ctx):
    timeout.setup(ctx)


@service.command(r"!g (?P<term>.+?)(?: #(?P<num>\d+))?$")
@service.command(r"(?:search|google)(?: for)? (?P<term>.+?)(?: \((?P<num>\d+)\))?\??$", mention=True)
@background
def search(ctx, term, num: int=None):
    """
    Google.

    Search for the given terms on Google. If a number is given, it will display
    that result.
    """

    if not timeout.handle(ctx):
        return

    r = requests.get(
        "https://www.googleapis.com/customsearch/v1",
        params={
            "key": ctx.config.api_key,
            "cx": ctx.config.cx,
            "q": term,
            "safe": ctx.config.safesearch,
        }
    ).json()

    results = r.get("items", [])

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

    ctx.respond(ctx._("(#{num} of {total}) {title}: {url}").format(
        title=results[num]["title"],
        url=results[num]["link"],
        num=num + 1,
        total=total
    ))
