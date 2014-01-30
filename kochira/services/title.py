import re
import requests
from lxml import etree

from ..service import Service
from io import BytesIO

service = Service(__name__)

HEADERS = {
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.8; rv:23.0) Gecko/20130426 Firefox/23.0'
}

DESPACE_EXPR = re.compile(r"\s+")

@service.register_command(r'.*(?P<url>http[s]?://[^\s<>"]+|www\.[^\s<>"]+)')
def detect_url(client, target, origin, url):
    if not (url.startswith("http:") or url.startswith("https:")):
        url = "http://" + url

    try:
        resp = requests.head(url, headers=HEADERS, verify=False)
    except requests.RequestException as e:
        client.message(target, "\x02Error:\x02 " + str(e))

    content_type = resp.headers.get("content-type", "text/html").split(";")[0]

    if content_type not in ("text/html", "application/xhtml+xml"):
        client.message(target, "\x02Content Type:\x02 " + content_type)
        return

    resp = requests.get(url, headers=HEADERS, verify=False)

    parser = etree.HTMLParser()
    tree = etree.parse(BytesIO(resp.text.encode("utf-8")), parser)

    title = tree.xpath("/html/head/title/text()")

    if title:
        title = DESPACE_EXPR.sub(" ", title[0].replace("\n", " "))
    else:
        title = "(no title)"

    client.message(target, "\x02Title:\x02 " + title)
