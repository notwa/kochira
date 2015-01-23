"""
URL scanner.

Fetches and displays metadata for web pages, images and more.
"""

import humanize
import re
import requests
import tempfile
from datetime import timedelta
from bs4 import BeautifulSoup
from PIL import Image

from kochira import config
from kochira.service import Service, background, Config

service = Service(__name__, __doc__)


@service.config
class Config(Config):
    max_size = config.Field(doc="Maximum request size.", default=5 * 1024 * 1024)


HEADERS = {
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.8; rv:23.0) Gecko/20130426 Firefox/23.0'
}

def handle_html(content):
    soup = BeautifulSoup(content)

    title = None

    if soup.title is not None:
        title = re.sub(r"\s+", " ", soup.title.string.strip())

    if not title:
        title = "(no title)"

    return "\x02Web Page Title:\x02 {title}".format(
        title=title
    )


def get_num_image_frames(im):
    try:
        while True:
             im.seek(im.tell() + 1)
    except EOFError:
        pass

    return im.tell()


def handle_image(content):
    with tempfile.NamedTemporaryFile() as f:
        f.write(content)
        im = Image.open(f.name)

    nframes = get_num_image_frames(im)

    info = "\x02Image Info:\x02 {w} x {h}; {size}".format(
        size=humanize.naturalsize(len(content)),
        w=im.size[0],
        h=im.size[1]
    )

    if nframes > 1:
        info += "; animated {t}, {n} frames".format(
            n=nframes,
            t=timedelta(seconds=nframes * im.info["duration"] // 1000)
        )

    return info


HANDLERS = {
    "text/html": handle_html,
    "application/xhtml+xml": handle_html,
    "image/jpeg": handle_image,
    "image/png": handle_image,
    "image/gif": handle_image,
    "image/webp": handle_image
}

@service.hook("channel_message")
@background
def detect_urls(ctx, origin, target, message):
    found_info = {}

    urls = re.findall(r'http[s]?://[^\s<>"]+|www\.[^\s<>"]+', message)

    for i, url in enumerate(urls):
        if not (url.startswith("http:") or url.startswith("https:")):
            url = "http://" + url

        if url not in found_info:
            try:
                url = ''.join([i for i in url if 31 < ord(i) < 127])
                resp = requests.head(url, headers=HEADERS, verify=False)
            except requests.RequestException as e:
                info = "\x02Error:\x02 " + str(e)
            else:
                content_type = resp.headers.get("content-type", "text/html").split(";")[0]

                if content_type in HANDLERS:
                    resp = requests.get(url, headers=HEADERS, verify=False,
                                        stream=True)
                    content = b""

                    for chunk in resp.iter_content(2048):
                        content += chunk
                        if len(content) > ctx.config.max_size:
                            resp.close()
                            info = "\x02Content Type:\x02 " + content_type
                            continue

                    info = HANDLERS[content_type]()
                else:
                    info = "\x02Content Type:\x02 " + content_type
            found_info[url] = info
        else:
            info = found_info[url]

        if len(urls) == 1:
            ctx.message(info)
        else:
            ctx.message("{info} ({i} of {num})".format(
                i=i + 1,
                num=len(urls),
                info=info
            ))
