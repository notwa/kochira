import re
import requests
import mimetypes
import tempfile
from lxml import etree
from PIL import Image

from ..service import Service, background

from io import BytesIO

service = Service(__name__)

HEADERS = {
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.8; rv:23.0) Gecko/20130426 Firefox/23.0'
}

DESPACE_EXPR = re.compile(r"\s+")

def handle_html(resp):
    parser = etree.HTMLParser()
    tree = etree.parse(BytesIO(resp.content), parser)

    title = tree.xpath("/html/head/title/text()")

    if title:
        title = DESPACE_EXPR.sub(" ", title[0].replace("\n", " "))
    else:
        title = "(no title)"

    return "\x02Web Page Title:\x02 {title}".format(
        title=title
    )


def handle_image(resp):
    with tempfile.NamedTemporaryFile(
        suffix=mimetypes.guess_extension(resp.headers["content-type"])
    ) as f:
        f.write(resp.content)
        im = Image.open(f.name)

    return "\x02Image Size:\x02 {w} x {h}".format(
        w=im.size[0],
        h=im.size[1]
    )


HANDLERS = {
    "text/html": handle_html,
    "application/xhtml+xml": handle_html,
    "image/jpeg": handle_image,
    "image/png": handle_image,
    "image/gif": handle_image
}

@service.hook("message")
@background
def detect_urls(client, target, origin, message):
    found_info = {}

    urls = re.findall(r'http[s]?://[^\s<>"]+|www\.[^\s<>"]+', message)

    for i, url in enumerate(urls):
        if not (url.startswith("http:") or url.startswith("https:")):
            url = "http://" + url

        if url not in found_info:
            try:
                resp = requests.head(url, headers=HEADERS, verify=False)
            except requests.RequestException as e:
                info = "\x02Error:\x02 " + str(e)
            else:
                content_type = resp.headers.get("content-type", "text/html").split(";")[0]

                if content_type in HANDLERS:
                    info = HANDLERS[content_type](requests.get(url, headers=HEADERS,
                                                                    verify=False))
                else:
                    info = "\x02Content Type:\x02 " + content_type
            found_info[url] = info
        else:
            info = found_info[url]

        if len(urls) == 1:
            client.message(target, info)
        else:
            client.message(target, "{info} ({i} of {num})".format(
                i=i + 1,
                num=len(urls),
                info=info
            ))
