"""
Wikipedia.

Extract a Wikipedia excerpt for the given query.
"""

import bs4
import requests

from kochira.service import Service, background

service = Service(__name__, __doc__)

@service.command(r"!w (?P<term>.+)")
@service.command(r"!wiki (?P<term>.+)")
@service.command(r"!wikipedia (?P<term>.+)")
@background
def lookup(ctx, term):
    """
    Look up.

    Look up the article.
    """

    r = requests.get("http://en.wikipedia.org/w/api.php", params={
        "format": "json",
        "action": "query",
        "prop": "extracts|info",
        "inprop": "url",
        "rawcontinue": True,
        "redirects": True,
        "titles": term
    }).json()

    page, *_ = r["query"]["pages"].values()
    
    if "missing" in page:
        ctx.respond(ctx._("Couldn't find that."))
        return

    text, *_ = bs4.BeautifulSoup(page["extract"]).get_text().split("\n")

    ctx.respond(ctx._("{url}: {text}").format(url=page["canonicalurl"], text=text))
