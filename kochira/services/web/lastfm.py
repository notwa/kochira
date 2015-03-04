"""
Last.fm now playing and music comparisons.

Allow users to display their now playing status and compare music tastes using
Last.fm.
"""

import requests
import gzip
import humanize
from datetime import datetime
from lxml import etree

from kochira import config
from kochira.userdata import UserData
from kochira.service import Service, background, Config, coroutine

service = Service(__name__, __doc__)

@service.config
class Config(Config):
    api_key = config.Field(doc="Last.fm API key.")


def query_lastfm(api_key, method, arguments):
    params = arguments.copy()
    params.update({
        "method": method,
        "api_key": api_key
    })

    r = requests.get(
        "http://ws.audioscrobbler.com/2.0/",
        params=params,
        stream=True
    )

    return etree.parse(gzip.GzipFile(fileobj=r.raw))


def get_compare_users(api_key, user1, user2):
    res = query_lastfm(
        api_key,
        "tasteometer.compare",
        {
            "type1": "user",
            "type2": "user",
            "value1": user1,
            "value2": user2
        }
    )

    comparison = res.xpath("/lfm[@status='ok']/comparison/result")

    if comparison:
        comparison, = comparison

        score, = comparison.xpath("score/text()")
        artists = comparison.xpath("artists/artist/name/text()")

        return {
            "user1": user1,
            "user2": user2,
            "score": float(score),
            "artists": artists
        }

    return None


def get_user_now_playing(api_key, user):
    res = query_lastfm(
        api_key,
        "user.getRecentTracks",
        {
            "user": user,
            "limit": 1
        }
    )

    track = res.xpath("/lfm[@status='ok']/recenttracks/track[@nowplaying='true']")

    now_playing = True

    if not track:
        track = res.xpath("/lfm[@status='ok']/recenttracks/track")
        now_playing = False

    if track:
        track = track[0]

        artist, = track.xpath("artist/text()")
        name, = track.xpath("name/text()")
        album, = track.xpath("album/text()") or [None]
        ts, = track.xpath("date/@uts") or [None]

        ts = int(ts) if ts is not None else None

        # get track info
        track_tags_r = query_lastfm(
            api_key,
            "track.getTopTags", {
                "artist": artist,
                "track": name
            }
        )
        tags = track_tags_r.xpath("/lfm[@status='ok']/toptags/tag/name/text()")

        track_info_r = query_lastfm(
            api_key,
            "track.getInfo", {
                "username": user,
                "artist": artist,
                "track": name
            }
        )
        info = track_info_r.xpath("/lfm[@status='ok']/track")

        if info:
            info, = info

            user_playcount, = info.xpath("userplaycount/text()") or [0]
            user_playcount = int(user_playcount)

            user_loved, = info.xpath("userloved/text()") or [0]
            user_loved = int(user_loved)
        else:
            user_playcount = 0
            user_loved = 0

        return {
            "user": user,
            "artist": artist,
            "name": name,
            "album": album,
            "tags": tags,
            "ts": ts,
            "user_playcount": user_playcount,
            "user_loved": user_loved,
            "now_playing": now_playing
        }

    return None


def escape_quotes(s):
    return s.replace("\"", "\\\"")


def make_spotify_query(params):
    return " ".join("{}:\"{}\"".format(k, escape_quotes(v))
                    for k, v in params.items())


def spotify_search(**params):
    return requests.get("https://api.spotify.com/v1/search", params={
        "q": make_spotify_query(params),
        "type": "track"
    }).json()["tracks"]["items"]


@coroutine
def get_lfm_username(client, who):
    user_data = yield UserData.lookup_default(client, who)
    return user_data.get("lastfm_user", who)


@service.command(r"!lfm (?P<lfm_username>\S+)$")
@service.command(r"my last\.fm username is (?P<lfm_username>\S+)$", mention=True)
@coroutine
def setup_user(ctx, lfm_username):
    """
    Set username.

    Associate a Last.fm username with your nickname.
    """

    try:
        user_data = yield UserData.lookup(ctx.client, ctx.origin)
    except UserData.DoesNotExist:
        ctx.respond(ctx._("You must be logged in to set your Last.fm username."))
        return

    user_data["lastfm_user"] = lfm_username
    user_data.save()

    ctx.respond(ctx._("You have been associated with the Last.fm username {user}.").format(user=lfm_username))


@service.command(r"!lfm$")
@service.command(r"what is my last\.fm username\??$", mention=True)
@coroutine
def check_user(ctx):
    """
    Now playing.

    Get the currently playing song for a user.
    """

    try:
        user_data = yield UserData.lookup(ctx.client, ctx.origin)
    except UserData.DoesNotExist:
        ctx.respond(ctx._("You must be logged in to set your Last.fm username."))
        return

    if "lastfm_user" not in user_data:
        ctx.respond(ctx._("You don't have a Last.fm username associated with your nickname. Please use \"!lfm\" to associate one."))
        return

    ctx.respond(ctx._("Your nickname is associated with {user}.").format(user=user_data["lastfm_user"]))


@service.command(r"!tasteometer (?P<user1>\S+) (?P<user2>\S+)$")
@service.command(r"!tasteometer (?P<user2>\S+)$")
@service.command(r"compare my last\.fm with (?P<user2>\S+)$", mention=True)
@service.command(r"compare (?P<user1>\S+) and (?P<user2>\S+) on last\.fms$", mention=True)
@background
@coroutine
def compare_users(ctx, user2, user1=None):
    """
    Tasteometer.

    Compare the music tastes of two users.
    """
    if user1 is None:
        user1 = ctx.origin

    lfm1 = yield ctx.bot.defer_from_thread(get_lfm_username, ctx.client, user1)
    lfm2 = yield ctx.bot.defer_from_thread(get_lfm_username, ctx.client, user2)

    comparison = get_compare_users(ctx.config.api_key, lfm1, lfm2)

    if comparison is None:
        ctx.respond(ctx._("Couldn't compare."))
        return

    ctx.respond(ctx._("{user1} ({lfm1}) and {user2} ({lfm2}) are {score:.2%} similar: {artists}").format(
        user1=user1,
        lfm1=lfm1,
        user2=user2,
        lfm2=lfm2,
        score=comparison["score"],
        artists=", ".join(comparison["artists"])
    ))


@service.command(r"!np$")
@service.command(r"!np (?P<who>\S+)$")
@service.command(r"what am i playing\??$", mention=True)
@service.command(r"what is (?P<who>\S+) playing\??$", mention=True)
@background
@coroutine
def now_playing(ctx, who=None):
    """
    Get username.

    Get your Last.fm username.
    """
    if who is None:
        who = ctx.origin

    lfm = yield get_lfm_username(ctx.client, who)
    track = get_user_now_playing(ctx.config.api_key, lfm)

    if track is None:
        ctx.respond(ctx._("{who} ({lfm}) has never scrobbled anything.").format(
            who=who,
            lfm=lfm
        ))
        return

    spotify_results = spotify_search(title=track["name"], artist=track["artist"])
    spotify_url = spotify_results[0]["external_urls"]["spotify"] if spotify_results else None

    track_descr = ctx._("\x02{name}\x02 by \x02{artist}\x02{album}{tags} (played {playcount} time{s})").format(
        name=track["name"],
        artist=track["artist"],
        album=ctx._(" on \x02{album}\x02").format(album=track["album"]) if track["album"] else "",
        tags=ctx._(" (tags: {tags})").format(tags=", ".join(track["tags"][:5])) if track["tags"] else "",
        playcount=track["user_playcount"],
        s="s" if track["user_playcount"] != 1 else ""
    )

    if not track["now_playing"]:
        ctx.respond(ctx._("{who} ({lfm}) was playing {descr} about {dt}{spotify}").format(
            who=who,
            lfm=lfm,
            dt=humanize.naturaltime(datetime.fromtimestamp(track["ts"])),
            descr=track_descr,
            spotify=": " + spotify_url if spotify_url is not None else ""
        ))
    else:
        ctx.respond(ctx._("{who} ({lfm}) is playing {descr}{spotify}").format(
            who=who,
            lfm=lfm,
            descr=track_descr,
            spotify=": " + spotify_url if spotify_url is not None else ""
        ))
