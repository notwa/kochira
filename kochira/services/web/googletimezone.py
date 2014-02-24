"""
Google time zone.

Get time zone information for places.
"""

import requests
import time
from datetime import datetime

from kochira import config
from kochira.service import Service, background, Config, coroutine
from kochira.userdata import UserData

service = Service(__name__, __doc__)


@service.command(r"!time(?: (?P<where>.+))?")
@service.command(r"time(?: (?:for|in) (?P<where>.+))?", mention=True)
@service.command(r"when is (?P<where>.+)\??", mention=True)
@background
@coroutine
def timezone(ctx, where=None):
    """
    Time.

    Get the time for a location.
    """

    if where is None:
        where = ctx.origin

    try:
        geocode = ctx.provider_for("geocode")
    except KeyError:
        ctx.respond(ctx._("Sorry, I don't have a geocode provider loaded."))
        return

    results = yield geocode(where)

    if not results:
        ctx.respond(ctx._("I don't know where \"{where}\" is.").format(
            where=where
        ))
        return

    result = results[0]

    location = result["geometry"]["location"]
    formatted_address = result["formatted_address"]

    now = time.time()

    resp = requests.get(
        "https://maps.googleapis.com/maps/api/timezone/json",
        params={
            "sensor": "false",
            "location": "{lat:.10},{lng:.10}".format(**location),
            "timestamp": now
        }
    ).json()

    if resp["status"] != "OK":
        ctx.respond(ctx._("Received an error code: {status}").format(
            status=resp["status"]
        ))
        return

    ctx.respond(ctx._("The time in {place} ({timezone}) is: {time}.").format(
        place=formatted_address,
        timezone=resp["timeZoneName"],
        time=datetime.utcfromtimestamp(now + resp["rawOffset"] + resp["dstOffset"]).strftime(ctx._("%H:%M on %A, %B %d, %Y"))
    ))
