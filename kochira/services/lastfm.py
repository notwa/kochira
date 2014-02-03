import requests
from urllib.parse import urlencode
from peewee import CharField
from lxml import etree
from io import BytesIO

from ..db import Model
from ..service import Service, background

service = Service(__name__)


class LastfmProfile(Model):
    who = CharField(255)
    network = CharField(255)
    lastfm_user = CharField(255)

    class Meta:
        indexes = (
            (("who", "network"), True),
        )


@service.setup
def initialize_model(bot):
    LastfmProfile.create_table(True)


def query_lastfm(method, arguments):
    r = requests.get("http://ws.audioscrobbler.com/2.0/?" + urlencode({
        "method": method,
        "api_key": "ebfbda6fb42b69b084844b567830513b",
    }) + "&" + urlencode(arguments))

    return etree.parse(BytesIO(r.content))


def get_compare_users(user1, user2):
    res = query_lastfm("tasteometer.compare", {"type1": "user", "type2": "user", "value1": user1, "value2": user2, })

    score = res.xpath("/lfm/comparison/result/score/text()")[0]
    artists = res.xpath('/lfm/comparison/result/artists/artist/name/text()')

    return "[{user1} vs {user2}] {score:.2%} -- {artists}".format(user1=user1, user2=user2, score=float(score), artists=", ".join(artists))


def get_user_now_playing(user):
    res = query_lastfm("user.getRecentTracks", {"user": user, "limit": 1, })
    track = res.xpath("/lfm/recenttracks/track[@nowplaying='true']")

    if len(track) > 0:
        track = track[0]

        artist = track.xpath("artist/text()")[0]
        name = track.xpath("name/text()")[0]
        album = track.xpath("album/text()")[0]

        # get track info
        track_tags_r = query_lastfm("track.getTopTags", { "artist": artist, "track": name, })
        tags = track_tags_r.xpath("/lfm/toptags/tag/name/text()")

        return "[{user}]: {artist} - {name} [{album}] ({tags})".format(user=user, artist=artist, name=name, album=album, tags=", ".join(tags[:5]))

    return "[{user}] is not playing anything :( needs moar SCROBBLING".format(user=user)


@service.command(r".lfm (?P<lfm_username>\S+)$", mention=False)
@background
def setup_user(client, target, origin, lfm_username):
    try:
        profile = LastfmProfile.get(LastfmProfile.network == client.network,
                              LastfmProfile.who == origin)
    except LastfmProfile.DoesNotExist:
        profile = LastfmProfile.create(network=client.network, who=origin,
                                 lastfm_user=lfm_username)

    profile.lastfm_user = lfm_username
    profile.save()

    client.message(target, "{origin}: last.fm username set to {user}.".format(
        origin=origin,
        user=lfm_username
    ))


@service.command(r".compare (?P<user1>\S+)$", mention=False)
@service.command(r".compare (?P<user1>\S+) (?P<user2>\S+)$", mention=False)
@background
def compare_users(client, target, origin, user1, user2=None):
    result = ""

    if user2:
        # compare 2 different users
        # looks up profiles from IRC usernames, otherwise just passes usernames as is
        try:
            profile = LastfmProfile.get(LastfmProfile.network == client.network,
                              LastfmProfile.who == user1)

            user1 = profile.lastfm_user
        except LastfmProfile.DoesNotExist:
            pass

        try:
            profile = LastfmProfile.get(LastfmProfile.network == client.network,
                              LastfmProfile.who == user2)

            user2 = profile.lastfm_user
        except LastfmProfile.DoesNotExist:
            pass

        result = get_compare_users(user1, user2)
    else:
        # compare current user against other user
        from_user = ""

        try:
            profile = LastfmProfile.get(LastfmProfile.network == client.network,
                              LastfmProfile.who == origin)

            from_user = profile.lastfm_user
        except LastfmProfile.DoesNotExist:
            client.message(target, "Setup your damn last.fm username with .lfm username")
            return

        try:
            profile = LastfmProfile.get(LastfmProfile.network == client.network,
                              LastfmProfile.who == user1)

            user1 = profile.lastfm_user
        except LastfmProfile.DoesNotExist:
            pass

        result = get_compare_users(from_user, user1)

    client.message(target, "last.fm: {0}".format(result))


@service.command(r".np$", mention=False)
@background
def now_playing(client, target, origin):
    try:
        profile = LastfmProfile.get(LastfmProfile.network == client.network,
                          LastfmProfile.who == origin)

        result = get_user_now_playing(profile.lastfm_user)

        client.message(target, "last.fm: {0}".format(result))

    except LastfmProfile.DoesNotExist:
        client.message(target, "Setup your damn last.fm username with .lfm username")
        return





