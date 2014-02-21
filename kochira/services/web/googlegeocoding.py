"""
Geocoding.

Look up and reverse look up addresses.
"""

import requests

from kochira import config
from kochira.service import Service, background, Config, coroutine
from kochira.userdata import UserData

service = Service(__name__, __doc__)


@service.config
class Config(Config):
    api_key = config.Field(doc="Google API key.")


@service.provides("GeocodingError")
class GeocodingError(Exception):
    """
    An exception thrown when geocoding fails.
    """
    pass


@service.provides("geocode")
def geocode(ctx, address):
    """
    Geocode an address.
    """
    resp = requests.get(
        "https://maps.googleapis.com/maps/api/geocode/json",
        params={
            "address": address,
            "sensor": "false"
        }
    ).json()

    if resp["status"] == "ZERO_RESULTS":
        return []

    if resp["status"] == "OK":
        return resp["results"]

    raise GeocodingError(resp["status"])


@service.command(r"where is (?P<place>.+)\??", mention=True)
@background
@coroutine
def get_location(ctx, place):
    """
    Get location.

    Get a location using geocoding.
    """

    who = None
    user_data = yield ctx.bot.defer_from_thread(UserData.lookup_default, ctx.client, place)

    if "location" in user_data:
        location = user_data["location"]

        ctx.respond(ctx._("{who} set their location to {formatted_address} ({lat:.10}, {lng:.10}).").format(
            who=place,
            **location
        ))
        return

    results = ctx.provider_for("geocode")(place)

    if not results:
        ctx.respond(ctx._("I don't know where \"{place}\" is.") .format(place=place))
        return

    result = results[0]

    if who is not None:
        fmt = ctx._("{who} set their location to {formatted_address} ({lat:.10}, {lng:.10}).")
    else:
        fmt = ctx._("Found \"{place}\" at {formatted_address} ({lat:.10}, {lng:.10}).")
    ctx.respond(fmt.format(
        who=who,
        place=place,
        formatted_address=result["formatted_address"],
        lat=float(result["geometry"]["location"]["lat"]),
        lng=float(result["geometry"]["location"]["lng"])
    ))


@service.command(r"i live (?:in|at) (?P<place>.+)", mention=True)
@service.command(r"my location is (?P<place>.+)", mention=True)
@background
@coroutine
def set_location(ctx, place):
    """
    Set location.

    Set your coordinates using geocoding.
    """

    try:
        user_data = yield ctx.bot.defer_from_thread(UserData.lookup, ctx.client, ctx.origin)
    except UserData.DoesNotExist:
        ctx.respond(ctx._("You need to be authenticated to set your location."))
        return

    results = ctx.provider_for("geocode")(place)
    if not results:
        ctx.respond(ctx._("I don't know where \"{place}\" is.").format(place=place))
        return

    result = results[0]
    location = {
        "lat": float(result["geometry"]["location"]["lat"]),
        "lng": float(result["geometry"]["location"]["lng"]),
        "formatted_address": result["formatted_address"]
    }

    user_data["location"] = location

    ctx.bot.defer_from_thread(user_data.save)
    ctx.respond(ctx._("Okay, set your location to {formatted_address} ({lat:.10}, {lng:.10}).").format(**location))


@service.command(r"find (?P<what>.+?) near (?:me|(?P<place>.+?))(?: \((?P<num>\d+)\))?", mention=True)
@service.command(r"find (?P<what>.+?) within (?P<radius>\d+) ?m of (?:me|(?P<place>.+?))(?: \((?P<num>\d+)\))?", mention=True)
@background
@coroutine
def nearby_search(ctx, what, place=None, radius : int=None, num : int=None):
    """
    Nearby search.

    Search for interesting places in an area.
    """
    if radius is None:
        radius = 1000

    if place is None:
        try:
            user_data = yield ctx.bot.defer_from_thread(UserData.lookup, ctx.client, ctx.origin)
        except UserData.DoesNotExist:
            location = None
        else:
            location = user_data.get("location", None)

        if location is None:
            ctx.respond(ctx._("I don't know where you are."))
            return
    else:
        user_data = yield ctx.bot.defer_from_thread(UserData.lookup_default, ctx.client, place)
        location = user_data.get("location")

        if location is None:
            results = ctx.provider_for("geocode")(place)

            if not results:
                ctx.respond(ctx._("I don't know where \"{where}\" is.").format(where=place))
                return

            location = results[0]["geometry"]["location"]

    resp = requests.get(
        "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
        params={
            "key": ctx.config.api_key,
            "radius": radius,
            "sensor": "false",
            "location": "{lat:.10},{lng:.10}".format(**location),
            "keyword": what
        }
    ).json()

    if resp["status"] == "ZERO_RESULTS":
        ctx.respond(ctx._("Couldn't find anything."))
        return

    if resp["status"] != "OK":
        ctx.respond(ctx._("Received an error code: {status}").format(
            status=resp["status"]
        ))
        return

    results = resp["results"]

    if num is None:
        num = 1

    # offset definition
    num -= 1
    total = len(results)

    result = results[num]

    if num >= total or num < 0:
        ctx.respond(ctx._("Can't find that location of \"{place}\".").format(place=place))
        return

    ctx.respond(ctx._("{name}, {vicinity} ({types}) ({num} of {total})").format(
        name=result["name"],
        vicinity=result["vicinity"],
        types=", ".join(result["types"]),
        num=num + 1,
        total=total
    ))
