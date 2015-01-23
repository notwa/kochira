"""
YouTube search.

Run queries on YouTube and return results.
"""

import requests

from kochira import config
from kochira.service import Service, background, Config, coroutine
from kochira.userdata import UserData

service = Service(__name__, __doc__)


@service.config
class Config(Config):
    api_key = config.Field(doc="Google API key.")


@service.command(r"!yt (?P<term>.+?)(?: (?P<num>\d+))?$")
@service.command(r"youtube search(?: for)? (?P<term>.+?)(?: \((?P<num>\d+)\))?\??$", mention=True)
@background
def search(ctx, term, num: int=None):
    """
    YouTube search.

    Search for the given terms on YouTube. If a number is given, it will display
    that result.
    """

    r = requests.get(
        "https://www.googleapis.com/youtube/v3/search",
        params={
            "key": ctx.config.api_key,
            "part": "snippet",
            "type": "youtube#video",
            "q": term
        }
    ).json()

    results = r.get("items", [])

    if not results:
        ctx.respond(ctx._("Couldn't find anything matching \"{term}\".").format(term=term))
        return

    if num is None:
        num = 1

    num -= 1
    total = len(results)

    if num >= total or num < 0:
        ctx.respond(ctx._("Couldn't find anything matching \"{term}\".").format(term=term))
        return

    r = requests.get(
        "https://www.googleapis.com/youtube/v3/videos",
        params={
            "key": ctx.config.api_key,
            "part": "statistics",
            "id": results[num]["id"]["videoId"]
        }
    ).json()

    statistics, = r["items"]
    statistics = statistics["statistics"]

    ctx.respond(ctx._("({num} of {total}) {title} (+{likes}/-{dislikes}, {views} views): http://youtu.be/{video_id}").format(
        title=results[num]["snippet"]["title"],
        likes=statistics["likeCount"],
        dislikes=statistics["dislikeCount"],
        views=statistics["viewCount"],
        video_id=results[num]["id"]["videoId"],
        num=num + 1,
        total=total
    ))
