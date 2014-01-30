import re
import requests
from urllib.parse import urlencode
from lxml import etree
from io import BytesIO

from ..service import Service

service = Service(__name__)

XPATH_EXPR = "/queryresult[@success='true']/pod[@primary='true']/subpod[1]/plaintext/text()"

@service.register_command(r"~~(?P<query>.+)$", background=True)
@service.register_command(r"!wa (?P<query>.+)$", background=True)
@service.register_command(r"(?:compute|calculate|mathify) (?P<query>.+)$", mention=True, background=True)
def query(client, target, origin, query):
    config = service.config_for(client.bot)

    resp = requests.get(url="http://api.wolframalpha.com/v2/query?" + urlencode({
        "input":    query,
        "appid":    config["appid"],
        "format":   "plaintext"
    }))

    tree = etree.parse(BytesIO(resp.text.encode("utf-8")))

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
