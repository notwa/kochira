import requests
import gzip
from peewee import CharField
from lxml import etree

from ..db import Model
from ..service import Service, background

service = Service(__name__)


class LastFMProfile(Model):
    who = CharField(255)
    network = CharField(255)
    lastfm_user = CharField(255)

    class Meta:
        indexes = (
            (("who", "network"), True),
        )


@service.setup
def initialize_model(bot):
    LastFMProfile.create_table(True)


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

    if len(comparison) > 0:
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

    if len(track) > 0:
        track, = track

        artist, = track.xpath("artist/text()")
        name, = track.xpath("name/text()")
        album, = track.xpath("album/text()") or [None]

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
            "tags": tags[:5]
        }

    return None


def get_lfm_username(client, who):
    try:
        profile = LastFMProfile.get(LastFMProfile.network == client.network,
                                    LastFMProfile.who == who)

        return profile.lastfm_user
    except LastFMProfile.DoesNotExist:
        return who


@service.command(r"!lfm (?P<lfm_username>\S+)$")
@service.command(r"my last\.fm username is (?P<lfm_username>\S+)$", mention=True)
def setup_user(client, target, origin, lfm_username):
    try:
        profile = LastFMProfile.get(LastFMProfile.network == client.network,
                                    LastFMProfile.who == origin)
    except LastFMProfile.DoesNotExist:
        profile = LastFMProfile.create(network=client.network, who=origin,
                                       lastfm_user=lfm_username)

    profile.lastfm_user = lfm_username
    profile.save()

    client.message(target, "{origin}: You have been associated with the Last.fm username {user}.".format(
        origin=origin,
        user=lfm_username
    ))

@service.command(r"!lfm$")
@service.command(r"what is my last\.fm username\??$", mention=True)
def check_user(client, target, origin):
    try:
        profile = LastFMProfile.get(LastFMProfile.network == client.network,
                                    LastFMProfile.who == origin)
    except LastFMProfile.DoesNotExist:
        client.message(target, "{origin}: You don't have a Last.fm username associated with it. Please use \"!lfm\" to associate one.".format(
            origin=origin
        ))
    else:
        client.message(target, "{origin}: Your nickname is associated with {user}.".format(
            origin=origin,
            user=profile.lastfm_user
        ))


@service.command(r"!tasteometer (?P<user1>\S+) (?P<user2>\S+)$")
@service.command(r"!tasteometer (?P<user2>\S+)$")
@service.command(r"compare my last\.fm with (?P<user2>\S+)$", mention=True)
@service.command(r"compare (?P<user1>\S+) and (?P<user2>\S+) on last\.fms$", mention=True)
@background
def compare_users(client, target, origin, user2, user1=None):
    config = service.config_for(client.bot)

    if user1 is None:
        user1 = origin

    comparison = get_compare_users(
        config["api_key"],
        get_lfm_username(client, user1),
        get_lfm_username(client, user2)
    )

    if comparison is None:
        client.message(target, "{origin}: Couldn't compare.".format(
            origin=origin
        ))
        return

    client.message(target, "{origin}: {user1} and {user2} are {score:.2%} similar: {artists}".format(
        origin=origin,
        user1=user1,
        user2=user2,
        score=comparison["score"],
        artists=", ".join(comparison["artists"])
    ))


@service.command(r"!np$")
@service.command(r"!np (?P<who>\S+)$")
@service.command(r"what am i playing\??$", mention=True)
@service.command(r"what is (?P<who>\S+) playing\??$", mention=True)
@background
def now_playing(client, target, origin, who=None):
    config = service.config_for(client.bot)

    if who is None:
        who = origin

    track = get_user_now_playing(config["api_key"], get_lfm_username(client, who))

    if track is None:
        client.message(target, "{origin}: {who} isn't playing anything right now.".format(
            origin=origin,
            who=who
        ))
        return

    client.message(target, "{origin}: {who} is playing: {artist} - {name}{album}{tags}".format(
        origin=origin,
        who=who,
        name=track["name"],
        artist=track["artist"],
        album=(" - " + track["album"]) if track["album"] else "",
        tags=(" (" + ", ".join(track["tags"]) + ")") if track["tags"] else ""
    ))
