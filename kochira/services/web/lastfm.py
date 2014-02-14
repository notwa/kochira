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

from pydle.async import blocking

from kochira import config
from kochira.userdata import UserData
from kochira.service import Service, background, Config

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

        return {
            "user": user,
            "artist": artist,
            "name": name,
            "album": album,
            "tags": tags[:5],
            "ts": ts,
            "now_playing": now_playing
        }

    return None


@blocking
def get_lfm_username(client, who):
    user_data = yield UserData.lookup_default(client, who)
    return user_data.get("lastfm_user", who)


@service.command(r"!lfm (?P<lfm_username>\S+)$")
@service.command(r"my last\.fm username is (?P<lfm_username>\S+)$", mention=True)
@blocking
def setup_user(client, target, origin, lfm_username):
    """
    Set username.

    Associate a Last.fm username with your nickname.
    """

    try:
        user_data = yield UserData.lookup(client, origin)
    except UserData.DoesNotExist:
        client.message(target, "{origin}: You must be authenticated to set your Last.fm username.".format(
            origin=origin
        ))
        return

    user_data["lastfm_user"] = lfm_username

    client.message(target, "{origin}: You have been associated with the Last.fm username {user}.".format(
        origin=origin,
        user=lfm_username
    ))


@service.command(r"!lfm$")
@service.command(r"what is my last\.fm username\??$", mention=True)
@blocking
def check_user(client, target, origin):
    """
    Now playing.

    Get the currently playing song for a user.
    """

    try:
        user_data = yield UserData.lookup(client, origin)
    except UserData.DoesNotExist:
        client.message(target, "{origin}: You must be authenticated to set your Last.fm username.".format(
            origin=origin
        ))
        return

    if "lastfm_user" not in user_data:
        client.message(target, "{origin}: You don't have a Last.fm username associated with your nickname. Please use \"!lfm\" to associate one.".format(
            origin=origin
        ))
        return

    client.message(target, "{origin}: Your nickname is associated with {user}.".format(
        origin=origin,
        user=user_data["lastfm_user"]
    ))


@service.command(r"!tasteometer (?P<user1>\S+) (?P<user2>\S+)$")
@service.command(r"!tasteometer (?P<user2>\S+)$")
@service.command(r"compare my last\.fm with (?P<user2>\S+)$", mention=True)
@service.command(r"compare (?P<user1>\S+) and (?P<user2>\S+) on last\.fms$", mention=True)
@background
@blocking
def compare_users(client, target, origin, user2, user1=None):
    """
    Tasteometer.

    Compare the music tastes of two users.
    """

    config = service.config_for(client.bot)

    if user1 is None:
        user1 = origin

    lfm1 = yield get_lfm_username(client, user1)
    lfm2 = yield get_lfm_username(client, user2)

    comparison = get_compare_users(config.api_key, lfm1, lfm2)

    if comparison is None:
        client.message(target, "{origin}: Couldn't compare.".format(
            origin=origin
        ))
        return

    client.message(target, "{origin}: {user1} ({lfm1}) and {user2} ({lfm2}) are {score:.2%} similar: {artists}".format(
        origin=origin,
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
@blocking
def now_playing(client, target, origin, who=None):
    """
    Get username.

    Get your Last.fm username.
    """

    config = service.config_for(client.bot)

    if who is None:
        who = origin

    lfm = yield get_lfm_username(client, who)

    track = get_user_now_playing(config.api_key, lfm)

    if track is None:
        client.message(target, "{origin}: {who} has never scrobbled anything.".format(
            origin=origin,
            who=who
        ))
        return

    track_descr = "{artist} - {name}{album}{tags}".format(
        name=track["name"],
        artist=track["artist"],
        album=(" - " + track["album"]) if track["album"] else "",
        tags=(" (" + ", ".join(track["tags"]) + ")") if track["tags"] else ""
    )

    if not track["now_playing"]:
        client.message(target, "{origin}: {who} ({lfm}) was playing{dt}: {descr}".format(
            origin=origin,
            who=who,
            lfm=lfm,
            dt=" about " + humanize.naturaltime(datetime.fromtimestamp(track["ts"])) if track["ts"] is not None else "",
            descr=track_descr
        ))
    else:
        client.message(target, "{origin}: {who} ({lfm}) is playing: {descr}".format(
            origin=origin,
            who=who,
            lfm=lfm,
            descr=track_descr
        ))
