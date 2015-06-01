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
import textwrap

from kochira import config
from kochira.service import Service, Config, background

service = Service(__name__, __doc__)


@service.config
class Config(Config):
    comic_server = config.Field(doc="Comic server to connect to.")
    clump_interval = config.Field(doc="Time to use for dialog clumping, in seconds.", type=float, default=10 * 60)
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


def make_comic_spec(title, lines, clump_interval, nicks):
    # do some initial clumping and limit number of stick figures to 3
    seen_names = set([])
    initial_lines = []
    
    for line in clump(lines,
                      datetime.datetime.fromtimestamp(0),
                      datetime.timedelta(seconds=clump_interval),
                      operator.attrgetter("ts")):
        initial_lines.append(line)
        seen_names.add(line.who)
    
        if len(seen_names) >= 3:
            break

    # determine conversation connectedness
    segment = []
    speakers = {initial_lines[0].who}

    for i in range(100):
    #while True:
        for line in initial_lines:
            possible_nicks = set(re.findall(r"(?:(?<=[^a-z_\-\[\]\\^{}|`])|^)[a-z_\-\[\]\\^{}|`][a-z0-9_\-\[\]\\^{}|`]*", line.text))
            possible_nicks.intersection_update(nicks)

            service.logger.info("CURRENT STATE: %s %s", possible_nicks, speakers)

            # a new person is talking to someone we know
            if possible_nicks.intersection(speakers) and line.who not in speakers:
                speakers.add(line.who)
                del segment[:]
                break
    
            # someone we know is talking to new people
            if line.who in speakers and possible_nicks:
                speakers.update(possible_nicks)
                del segment[:]
                break

            # nobody is talking to anyone, so we'll just add this line in and continue
            if line.who in speakers:
                segment.append(line)
    
        # we've collected all the lines now
        if segment:
            break
    
    # no connectivity, just render the whole comic
    if speakers == {initial_lines[0].who}:
        segment = initial_lines

    stick_figures = list(collections.Counter([
        entry.who for entry in segment]).keys())

    average_pondering = sum((next.ts - prev.ts).total_seconds()
                            for next, prev in zip(segment, segment[1:])) \
                        / len(segment)

    clumps = []

    for subclump in clump_many(segment, datetime.datetime.fromtimestamp(0),
                               datetime.timedelta(seconds=average_pondering),
                               operator.attrgetter("ts")):
        while subclump:
            clumps.append(subclump[:3])
            subclump = subclump[3:]

    return {
        "panels_per_row": 1 if len(clumps) == 1 else 2,
        "panel_width": 600,
        "panel_height": 600,
        "title": title,
        "title_size": 35,
        "panels": [{
            "stick_figures": stick_figures,
            "dialogs": [{
                "speaker": dialog.who,
                "text": "\n".join(textwrap.wrap(truncate_really_long_words(strip_control_codes(dialog.text)), 25))
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
                                 list(ctx.client.backlogs[ctx.target])[1:],
                                 ctx.config.clump_interval, ctx.client.channels[ctx.target].users)

    resp = requests.post(ctx.config.comic_server, stream=True, data=json.dumps(comic_spec))

    try:
        resp.raise_for_status()
    except:
        ctx.respond(ctx._("Couldn't generate a comic."))
        return

    ulim = requests.post("https://api.imgur.com/3/upload.json",
                         headers={"Authorization": "Client-ID " + ctx.config.imgur_clientid},
                         data={"image": resp.raw.read()}).json()

    if ulim["status"] != 200:
        ctx.respond(ctx._("Couldn't upload comic."))
    else:
        ctx.respond(ctx._("Comic: {url}".format(url=ulim["data"]["link"])))
