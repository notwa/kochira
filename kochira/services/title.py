import re
import requests
import mimetypes
import tempfile
from lxml import etree
from PIL import Image

from ..service import Service
from io import BytesIO

service = Service(__name__)

HEADERS = {
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.8; rv:23.0) Gecko/20130426 Firefox/23.0'
}

DESPACE_EXPR = re.compile(r"\s+")

def handle_html(client, target, origin, resp):
    parser = etree.HTMLParser()
    tree = etree.parse(BytesIO(resp.content), parser)

    title = tree.xpath("/html/head/title/text()")

    if title:
        title = DESPACE_EXPR.sub(" ", title[0].replace("\n", " "))
    else:
        title = "(no title)"

    client.message(target, "\x02Web Page Title:\x02 {title}".format(
        title=title
    ))


def handle_image(client, target, origin, resp):
    with tempfile.NamedTemporaryFile(
        suffix=mimetypes.guess_extension(resp.headers["content-type"])
    ) as f:
        f.write(resp.content)
        im = Image.open(f.name)

    client.message(target, "\x02Image Size:\x02 {w} x {h}".format(
        w=im.size[0],
        h=im.size[1]
    ))


HANDLERS = {
    "text/html": handle_html,
    "application/xhtml+xml": handle_html,
    "image/jpeg": handle_image,
    "image/png": handle_image,
    "image/gif": handle_image
}

@service.command(r'.*(?P<url>http[s]?://[^\s<>"]+|www\.[^\s<>"]+)', background=True)
def detect_url(client, target, origin, url):
    if not (url.startswith("http:") or url.startswith("https:")):
        url = "http://" + url

    try:
        resp = requests.head(url, headers=HEADERS, verify=False)
    except requests.RequestException as e:
        client.message(target, "\x02Error:\x02 " + str(e))

    content_type = resp.headers.get("content-type", "text/html").split(";")[0]

    if content_type not in HANDLERS and \
        content_type != mimetypes.guess_type(url):
        client.message(target, "\x02Content Type:\x02 " + content_type)
        return

    HANDLERS[content_type](client, target, origin,
                           requests.get(url, headers=HEADERS, verify=False))
