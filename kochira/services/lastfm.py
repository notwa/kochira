import requests
from urllib.parse import urlencode
from peewee import CharField
from lxml import etree
from io import BytesIO

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
    r = requests.get("http://ws.audioscrobbler.com/2.0/?" + urlencode({
        "method": method
    }) + "&" + urlencode(arguments))

    return etree.parse(BytesIO(r.content))


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

    score = res.xpath("/lfm/comparison/result/score/text()")[0]
    artists = res.xpath('/lfm/comparison/result/artists/artist/name/text()')

    return "[{user1} vs {user2}] {score:.2%}: {artists}".format(
        user1=user1,
        user2=user2,
        score=float(score),
        artists=", ".join(artists)
    )


def get_user_now_playing(api_key, user):
    res = query_lastfm(
        api_key,
        "user.getRecentTracks",
        {
            "user": user,
            "limit": 1
        }
    )
    track = res.xpath("/lfm/recenttracks/track[@nowplaying='true']")

    if len(track) > 0:
        track = track[0]

        artist = track.xpath("artist/text()")[0]
        name = track.xpath("name/text()")[0]
        album = track.xpath("album/text()")[0]

        # get track info
        track_tags_r = query_lastfm("track.getTopTags", { "artist": artist, "track": name, })
        tags = track_tags_r.xpath("/lfm/toptags/tag/name/text()")

        return "{user} is playing {name} by {artist} on {album} ({tags}).".format(
            user=user,
            artist=artist,
            name=name,
            album=album or "(unknown album)",
            tags=", ".join(tags[:5])
        )

    return "{user} is not playing anything.".format(user=user)


def get_lfm_username(client, who):
    try:
        profile = LastFMProfile.get(LastFMProfile.network == client.network,
                                    LastFMProfile.who == who)

        return profile.lastfm_user
    except LastFMProfile.DoesNotExist:
        return who

@service.command(r"i(?:'m| am) (?P<lfm_username>\S+) on last\.fm$")
@service.command(r"my last\.fm username is (?P<lfm_username>\S+)$")
def setup_user(client, target, origin, lfm_username):
    try:
        profile = LastFMProfile.get(LastFMProfile.network == client.network,
                                    LastFMProfile.who == origin)
    except LastFMProfile.DoesNotExist:
        profile = LastFMProfile.create(network=client.network, who=origin,
                                       lastfm_user=lfm_username)

    profile.lastfm_user = lfm_username
    profile.save()

    client.message(target, "{origin}: You have been associated with last.fm username {user}.".format(
        origin=origin,
        user=lfm_username
    ))


@service.command(r"compare my last\.fm with (?P<user1>\S+)$")
@service.command(r"compare (?P<user1>\S+) and (?P<user2>\S+) on last\.fms$")
@background
def compare_users(client, target, origin, user1, user2=None):
    config = service.config_for(client.bot)

    if user2 is not None:
        # compare 2 different users
        # looks up profiles from IRC usernames, otherwise just passes usernames as is
        user1 = get_lfm_username(client, user1)
        user2 = get_lfm_username(client, user2)
    else:
        user1 = get_lfm_username(client, origin)
        user2 = get_lfm_username(client, user1)

    client.message(target, "{origin}: {comparison}".format(
        origin=origin,
        comparison=get_compare_users(config["api_key"], user1, user2)
    ))


@service.command(r"!np$", mention=False)
@service.command(r"!np (?P<who>\S+)$", mention=False)
@service.command(r"what am i playing\??$")
@service.command(r"what is (?P<who>\S+) playing\??$")
@background
def now_playing(client, target, origin, who=None):
    config = service.config_for(client.bot)

    if who is None:
        who = origin

    client.message(target, "{origin}: {np}".format(
        origin=origin,
        np=get_user_now_playing(config["api_key"], get_lfm_username(who))
    ))
