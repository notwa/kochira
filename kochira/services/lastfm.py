import requests
from urllib.parse import urlencode, unquote
from peewee import CharField, TextField

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
        "format": "json",
    }) + "&" + urlencode(arguments)).json()
    return r


def get_compare_users(user1, user2):
    res = query_lastfm("tasteometer.compare", {"type1": "user", "type2": "user", "value1": user1, "value2": user2, })

    score = res['comparison']['result']['score']
    artists = [a['name'] for a in res['comparison']['result']['artists']['artist']]

    return "[{0} vs {1}] {2:.2%} -- {3}".format(user1, user2, float(score), ", ".join(artists))


def get_user_now_playing(user):
    res = query_lastfm("user.getRecentTracks", {"user": user, "limit": 1, })
    track = [t for t in res.get("recenttracks", {}).get("track", []) if t.get("@attr", {}).get("nowplaying", {}) == "true"]

    if len(track) > 0:
        track = track[0]

        artist = track["artist"]
        name = track["name"]
        album = track["album"]

        # get track info
        track_tags_r = query_lastfm("track.getTopTags", { "artist": artist, "track": name, })
        tags = [t['name'] for t in track_tags_r.get("toptags", {}).get("tag", [])]

        return "[{0}]: {1} - {2} [{3}] ({4})".format(user, artist, name, album, ", ".join(tags[:5]))

    return "[{0}] is not playing anything :( needs moar SCROBBLING".format(user)


@service.command(r".lfm (?P<lfm_username>.+)$", mention=False)
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





