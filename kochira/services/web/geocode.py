"""
Geocoding.

Look up and reverse look up addresses.
"""

import requests

from pydle.async import coroutine

from kochira import config
from kochira.service import Service, background, Config
from kochira.userdata import UserData

service = Service(__name__, __doc__)


@service.config
class Config(Config):
    api_key = config.Field(doc="Google API key.")


def geocode(address):
    return requests.get(
        "https://maps.googleapis.com/maps/api/geocode/json",
        params={
            "address": address,
            "sensor": "false"
        }
    ).json().get("results", [])


@service.command(r"where is (?P<place>.+)\??", mention=True)
@background
@coroutine
def get_location(client, target, origin, place):
    """
    Get location.

    Get a location using geocoding.
    """

    who = None

    user_data = yield client.bot.defer_from_thread(UserData.lookup_default, client, place)

    if "location" in user_data:
        location = user_data["location"]

        client.message(target, "{origin}: {who} set their location to {formatted_address} ({lat:.10}, {lng:.10}).".format(
            origin=origin,
            who=place,
            **location
        ))
        return

    results = geocode(place)

    if not results:
        client.message(target, "{origin}: I don't know where \"{place}\" is.".format(
            origin=origin,
            place=place
        ))
        return

    result = results[0]

    if who is not None:
        fmt = "{origin}: {who} set their location to {formatted_address} ({lat:.10}, {lng:.10})."
    else:
        fmt = "{origin}: Found \"{place}\" at {formatted_address} ({lat:.10}, {lng:.10})."

    client.message(target, fmt.format(
        origin=origin,
        who=who,
        place=place,
        formatted_address=result["formatted_address"],
        lat=float(result["geometry"]["location"]["lat"]),
        lng=float(result["geometry"]["location"]["lng"])
    ))


@service.command(r"my location is (?P<place>.+)", mention=True)
@background
@coroutine
def set_location(client, target, origin, place):
    """
    Set location.

    Set your coordinates using geocoding.
    """

    try:
        user_data = yield client.bot.defer_from_thread(UserData.lookup, client, origin)
    except UserData.DoesNotExist:
        client.message(target, "{origin}: You need to be authenticated to set your location.".format(
            origin=origin,
        ))
        return

    results = geocode(place)

    if not results:
        client.message(target, "{origin}: I don't know where \"{place}\" is.".format(
            origin=origin,
            place=place
        ))
        return

    result = results[0]

    location = {
        "lat": float(result["geometry"]["location"]["lat"]),
        "lng": float(result["geometry"]["location"]["lng"]),
        "formatted_address": result["formatted_address"]
    }

    user_data["location"] = location

    client.bot.defer_from_thread(user_data.save)

    client.message(target, "{origin}: Okay, set your location to {formatted_address} ({lat:.10}, {lng:.10}).".format(
        origin=origin,
        **location
    ))


@service.command(r"find (?P<what>.+?) near (?:me|(?P<place>.+))", mention=True)
@service.command(r"find (?P<what>.+?) within (?P<radius>\d+) ?m of (?:me|(?P<place>.+))", mention=True)
@background
@coroutine
def nearby_search(client, target, origin, what, place=None, radius : int=None):
    """
    Nearby search.

    Search for interesting places in an area.
    """
    if radius is None:
        radius = 1000

    config = service.config_for(client.bot, client.name, target)

    if place is None:
        try:
            user_data = yield client.bot.defer_from_thread(UserData.lookup, client, origin)
        except UserData.DoesNotExist:
            location = None
        else:
            location = user_data.get("location", None)

        if location is None:
            client.message(target, "{origin}: I don't know where you are.".format(
                origin=origin,
            ))
            return
    else:
        results = geocode(place)

        if not results:
            client.message(target, "{origin}: I don't know where \"{place}\" is.".format(
                origin=origin,
                place=place
            ))
            return

        location = results[0]["geometry"]["location"]

    results = requests.get(
        "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
        params={
            "key": config.api_key,
            "radius": radius,
            "sensor": "false",
            "location": "{lat:.10},{lng:.10}".format(**location),
            "keyword": what
        }
    ).json().get("results", [])

    if not results:
        client.message(target, "{origin}: Couldn't find anything.".format(
            origin=origin
        ))
        return

    result = results[0]

    client.message(target, "{origin}: {name}, {vicinity} ({types})".format(
        origin=origin,
        name=result["name"],
        vicinity=result["vicinity"],
        types=", ".join(result["types"])
    ))
