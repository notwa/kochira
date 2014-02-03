import re
import requests
from urllib.parse import urlencode
from lxml import etree
from io import BytesIO

from ..service import Service, background

service = Service(__name__)

@service.command(r"~~(?P<query>.+)$")
@service.command(r"!wa (?P<query>.+)$")
@service.command(r"(?:compute|calculate|mathify) (?P<query>.+)$", mention=True)
@background
def query(client, target, origin, query):
    config = service.config_for(client.bot)

    resp = requests.get(url="http://api.wolframalpha.com/v2/query?" + urlencode({
        "input": query,
        "appid": config["appid"],
        "format": "plaintext",
        "reinterpret": "true"
    }))

    tree = etree.parse(BytesIO(resp.content))

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
            client.message(target, "{origin}: | {line}".format(
                origin=origin,
                line=line
            ))
    else:
        client.message(target, "{origin}: {inp} = {primary}".format(
            origin=origin,
            inp=inp,
            primary=primary
        ))
