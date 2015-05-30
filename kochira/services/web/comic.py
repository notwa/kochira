"""
Comic generator.

Generates comics.
"""

import collections
import datetime
import json
import operator
import re
import requests

from kochira import config
from kochira.service import Service, Config, background

service = Service(__name__, __doc__)


@service.config
class Config(Config):
    comic_server = config.Field(doc="Comic server to connect to.")
    imgur_clientid = config.Field(doc="Client ID for use with Imgur.")


CONTROL_CODE_RE = re.compile(
    "\x1f|\x02|\x12|\x0f|\x16|\x03(?:\d{1,2}(?:,\d{1,2})?)?", re.UNICODE)


def strip_control_codes(s):
    return CONTROL_CODE_RE.sub("", s)


def truncate_really_long_words(s):
    return re.sub(r"(\S{30})\S*", "\\1...", s, re.UNICODE)


def clump(xs, init, delta, key=lambda x: x):
    for x in xs:
        k = key(x)
        if init - k < delta:
            yield x
        else:
            break
        init = k


def clump_many(xs, init, delta, key=lambda x: x):
    clumps = []
    current_clump = []
    clumps.append(current_clump)

    for x in xs:
        k = key(x)
        if init - k > delta:
            current_clump = []
            clumps.append(current_clump)

        current_clump.append(x)
        init = k

    return clumps


def make_comic_spec(title, lines):
    seen_names = set([])
    segment = []

    for line in clump(lines,
                     datetime.datetime.fromtimestamp(0),
                     datetime.timedelta(seconds=120),
                     operator.attrgetter("ts")):
        segment.append(line)
        seen_names.add(line.who)

        if len(seen_names) >= 3:
            break

    stick_figures = list(collections.Counter([
        entry.who for entry in segment]).keys())

    average_pondering = sum((next.ts - prev.ts).total_seconds()
                            for next, prev in zip(segment, segment[1:])) \
                        / len(segment)

    clumps = []

    for clump in clump_many(segment, datetime.datetime.fromtimestamp(0),
                            datetime.timedelta(seconds=average_pondering),
                            operator.attrgetter("ts")):
        while clump:
            clumps.append(clump[:3])
            clump = clump[3:]

    return {
        "panels_per_row": 2,
        "panel_width": 500,
        "panel_height": 500,
        "title": title,
        "title_size": 35,
        "panels": [{
            "num_stick_figures": len(stick_figures),
            "dialogs": [{
                "speaker": stick_figures.index(dialog.who),
                "text": truncate_really_long_words(strip_control_codes(dialog.text))
            } for dialog in reversed(panel)]
        } for panel in reversed(clumps)]
    }


@service.command("!comic")
@background
def comic(ctx):
    """
    Comic.
    
    Generate a comic.
    """
    comic_spec = make_comic_spec(ctx._("{channel}: the comic").format(channel=ctx.target),
                                 ctx.client.backlogs[ctx.target][1:])

    resp = requests.post(ctx.config.comic_server, stream=True, data=json.dumps(comic_spec))

    try:
        resp.raise_for_status()
    except:
        ctx.respond(ctx._("Couldn't generate a comic."))

    ulim = requests.post("https://api.imgur.com/3/upload.json",
                         headers={"Authorization": "Client-ID " + ctx.config.imgur_clientid},
                         data={"image": resp.raw.read()).json()

    if ulim["status"] != 200:
        ctx.respond(ctx._("Couldn't upload comic."))
    else:
        ctx.respond(ctx._("Comic: {url}".format(url=ulim["data"]["link"])))
