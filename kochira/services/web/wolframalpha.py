"""
Wolfram|Alpha query.

Runs queries on Wolfram|Alpha.
"""

import re
import requests
from lxml import etree

from kochira import config
from kochira.service import Service, background

service = Service(__name__, __doc__)

@service.config
class Config(config.Config):
    appid = config.Field(doc="Wolfram|Alpha application ID.")


@service.command(r"!wa (?P<query>.+)$")
@service.command(r"(?:compute|calculate|mathify) (?P<query>.+)$", mention=True)
@background
def compute(client, target, origin, query):
    """
    Compute.

    ::

        !wa <query>
        $bot: (compute|calculate|mathify) <query>

    Run a query on Wolfram|Alpha and display the result.
    """

    config = service.config_for(client.bot)

    resp = requests.get("http://api.wolframalpha.com/v2/query",
        params={
            "input": query,
            "appid": config.appid,
            "format": "plaintext",
            "reinterpret": "true"
        },
        stream=True
    )

    tree = etree.parse(resp.raw)

    result_node = tree.xpath("/queryresult[@success='true']")

    if not result_node:
        client.message(target, "{origin}: Couldn't compute that.".format(
            origin=origin
        ))
        return

    result_node, = result_node
    inp = " ".join(result_node.xpath("pod[@id='Input']/subpod[1]/plaintext/text()")).strip()
    primary = re.sub(
        r"(?<!\\)\\:([0-9a-fA-F]{4})",
        lambda x: chr(int(x.group(1), 16)),
        "\n".join(result_node.xpath("pod[@primary='true']/subpod[1]/plaintext/text()")).strip()
    ).split("\n")

    if len(primary) > 1:
        client.message(target, "{origin}: {inp}".format(
            origin=origin,
            inp=inp
        ))

        for line in primary:
            client.message(target, "{origin}: = {line}".format(
                origin=origin,
                line=line
            ))
    else:
        client.message(target, "{origin}: {inp} = {primary}".format(
            origin=origin,
            inp=inp,
            primary=primary[0]
        ))
