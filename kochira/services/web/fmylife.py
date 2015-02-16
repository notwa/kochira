"""
FMyLife.

Retrieves FMLs from FMyLife.
"""

import io
import requests
import lxml.etree

from urllib.parse import quote_plus
from kochira import config
from kochira.service import Service, background, Config

service = Service(__name__, __doc__)

@service.config
class Config(Config):
    api_key = config.Field(doc="FML API key.")
    language = config.Field(doc="Language to retrieve FML entries in.", default="en")


@service.command(r"!fml")
@service.command(r"fml", mention=True)
@service.command(r"f(?:uck)? my life", mention=True)
@background
def fml(ctx):
    """
    FML.

    Get a random FML entry.
    """

    r = requests.get("http://api.betacie.com/view/random/nocomment", params={
        "language": ctx.config.language,
        "key": ctx.config.api_key
    })
    r.raise_for_status()
    
    tree = lxml.etree.parse(io.BytesIO(r.text.encode("utf-8")))
    elem, = tree.xpath("items/item/text")

    ctx.respond(elem.text)
