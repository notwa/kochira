import re
import requests
from urllib.parse import urlencode
from lxml import etree
from io import BytesIO

from ..service import Service, background

service = Service(__name__)

XPATH_EXPR = "/queryresult[@success='true']/pod[@primary='true']/subpod[1]/plaintext/text()"

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

    result = tree.xpath(XPATH_EXPR)

    if result:
        result = "\n".join(result)
    else:
        result = "(no result)"

    prefix = "Wolfram|Alpha:"

    for line in result.split("\n"):
        line = re.sub(r"(?<!\\)\\:([0-9a-fA-F]{4})", lambda x: chr(int(x.group(1), 16)), line)
        client.message(target, "\x02{}\x02 {}".format(prefix, line))
        prefix = "↳"
