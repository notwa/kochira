"""
Geocoding.

Look up and reverse look up addresses.
"""

import re
import requests
import urllib.parse
from geopy.distance import vincenty, great_circle

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


def _geocode(where):
    resp = requests.get(
        "https://maps.googleapis.com/maps/api/geocode/json",
        params={
            "address": where,
            "sensor": "false"
        }
    ).json()

    if resp["status"] == "ZERO_RESULTS":
        return []

    if resp["status"] != "OK":
        raise GeocodingError(resp["status"])

    return resp["results"]


@service.provides("geocode")
@coroutine
def geocode(ctx, where):
    """
    Geocode an address.
    """
    location = None

    user_data = yield ctx.bot.defer_from_thread(UserData.lookup_default, ctx.client, where)
    location = user_data.get("location")

    if where is None and location is None:
        return []
    elif location is not None:
        result = _geocode("{lat},{lng}".format(**location))[0]
        result["formatted_address"] = location["formatted_address"]
        return [result]
    else:
        return _geocode(where)


@service.command(r"where is (?P<where>.+)\??", mention=True)
@background
@coroutine
def get_location(ctx, where):
    """
    Get location.

    Get a location using geocoding.
    """

    results = yield ctx.provider_for("geocode")(where)

    if not results:
        ctx.respond(ctx._("I don't know where \"{where}\" is.").format(
            where=where
        ))
        return

    result = results[0]

    ctx.respond(ctx._("Found \"{where}\" at {formatted_address} ({lat:.10}, {lng:.10}): https://www.google.com/maps/place/{quoted_address}/@{lat:.10},{lng:.10},15z").format(
        where=where,
        formatted_address=result["formatted_address"],
        quoted_address=urllib.parse.quote_plus(result["formatted_address"]),
        lat=float(result["geometry"]["location"]["lat"]),
        lng=float(result["geometry"]["location"]["lng"])
    ))


@service.command(r"i live (?:in|at) (?P<where>.+)", mention=True)
@service.command(r"my location is (?P<where>.+)", mention=True)
@background
@coroutine
def set_location(ctx, where):
    """
    Set location.

    Set your coordinates using geocoding.
    """

    try:
        user_data = yield ctx.bot.defer_from_thread(UserData.lookup, ctx.client, ctx.origin)
    except UserData.DoesNotExist:
        ctx.respond(ctx._("You need to be logged into NickServ to set your location."))
        return

    results = yield ctx.provider_for("geocode")(where)

    if not results:
        ctx.respond(ctx._("I don't know where \"{where}\" is.").format(
            where=where
        ))
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


@service.command(r"find (?P<what>.+?) (?:near|in) (?:me|(?P<where>.+?))(?: \((?P<num>\d+)\))?", mention=True)
@service.command(r"find (?P<what>.+?) within (?P<radius>\d+) ?m of (?:me|(?P<where>.+?))(?: \((?P<num>\d+)\))?", mention=True)
@background
@coroutine
def nearby_search(ctx, what, where=None, radius : int=None, num : int=None):
    """
    Nearby search.

    Search for interesting places in an area.
    """

    if where is None:
        where = ctx.origin

    if radius is None:
        radius = 1000

    results = yield ctx.provider_for("geocode")(where)

    if not results:
        ctx.respond(ctx._("I don't know where \"{where}\" is.").format(
            where=where
        ))
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
        ctx.respond(ctx._("Can't find that location of \"{where}\".").format(where=where))
        return

    ctx.respond(ctx._("{name}, {vicinity} ({types}) ({num} of {total})").format(
        name=result["name"],
        vicinity=result["vicinity"],
        types=", ".join(t.replace("_", " ") for t in result["types"]),
        num=num + 1,
        total=total
    ))


@service.command(r"distance(?: from (?P<start_loc>.+?))? to (?P<path>.+?)", mention=True)
@background
@coroutine
def distance(ctx, path, start_loc=None):
    """
    Distance.

    Compute the great-circle distance between two locations.
    """

    if start_loc is None:
        start_loc = ctx.origin

    start_results = yield ctx.provider_for("geocode")(start_loc)

    if not start_results:
        ctx.respond(ctx._("I don't know where \"{where}\" is.").format(
            where=start_loc
        ))
        return

    start_result = start_results[0]
    start_coords = start_result["geometry"]["location"]

    part_results = []
    for part in re.split(r"\s+to\s+", path):
        results = yield ctx.provider_for("geocode")(part)
        if not results:
            ctx.respond(ctx._("I don't know where \"{where}\" is.").format(
                where=end_loc
            ))
            return

        part_results.append(results[0])

    is_great_circle = False

    distance = 0

    for a, b in zip([start_result] + part_results, part_results):
        a_coords = a["geometry"]["location"]
        b_coords = b["geometry"]["location"]

        try:
            distance += vincenty((a_coords["lat"], a_coords["lng"]),
                                 (b_coords["lat"], b_coords["lng"])).km
        except ValueError:
            is_great_circle = True
            distance += great_circle((a_coords["lat"], a_coords["lng"]),
                                     (b_coords["lat"], b_coords["lng"])).km

    ctx.respond(ctx._("Distance from {start} to {end}: {approx}{distance:.3f} km").format(
        start=start_result["formatted_address"],
        end=ctx._(" to ").join(part["formatted_address"] for part in part_results),
        distance=distance,
        approx="~" if is_great_circle else ""
    ))
