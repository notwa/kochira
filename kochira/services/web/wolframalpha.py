"""
Wolfram|Alpha query.

Runs queries on Wolfram|Alpha.
"""

import re
import requests
from lxml import etree

from pydle.async import coroutine

from kochira import config
from kochira.service import Service, background, Config
from kochira.userdata import UserData

service = Service(__name__, __doc__)

@service.config
class Config(Config):
    appid = config.Field(doc="Wolfram|Alpha application ID.")


@service.command(r"!wa (?P<query>.+)$")
@service.command(r"(?:compute|calculate|mathify) (?:for (?P<who>\S+))?(?P<query>.+)$", mention=True)
@background
@coroutine
def compute(ctx, query, who=None):
    """
    Compute.

    Run a query on Wolfram|Alpha and display the result.
    """

    if who is not None:
        user_data = yield ctx.bot.defer_from_thread(UserData.lookup_default, ctx.client, who)

        if "location" not in user_data:
            ctx.respond("I don't have location information for {who}.".format(who=who))
            return
    else:
        try:
            user_data = yield ctx.bot.defer_from_thread(UserData.lookup, ctx.client, ctx.origin)
        except UserData.DoesNotExist:
            user_data = {}

    params = {
        "input": query,
        "appid": ctx.config.appid,
        "format": "plaintext",
        "reinterpret": "true"
    }

    location = user_data.get("location", None)
    if location is not None:
        params["latlong"] = "{lat},{lng}".format(**location)

    resp = requests.get("http://api.wolframalpha.com/v2/query",
        params=params,
        stream=True
    )

    tree = etree.parse(resp.raw)
    result_node = tree.xpath("/queryresult[@success='true']")

    if not result_node:
        ctx.respond("Couldn't compute that.")
        return

    result_node, = result_node

    out = re.sub(
        r"(?<!\\)\\:([0-9a-fA-F]{4})",
        lambda x: chr(int(x.group(1), 16)),

        "\n".join(result_node.xpath("pod[@id='Input']/subpod[1]/plaintext/text()")).strip() +
        " = " +
        "\n".join(result_node.xpath("pod[@primary='true']/subpod[1]/plaintext/text()")).strip()
    ).replace("\n", "; ")

    ctx.respond("{out}".format(out=out))
