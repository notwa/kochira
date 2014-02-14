"""
Geocoding.

Look up and reverse look up addresses.
"""

import requests
from html.parser import HTMLParser

from pydle.async import blocking
from kochira.service import Service, background
from kochira.userdata import UserData

service = Service(__name__, __doc__)

html_parser = HTMLParser()


@service.command(r"my location is (?P<place>.+)", mention=True)
@background
@blocking
def set_location(client, target, origin, place):
    """
    Set location.

    Set your coordinates using geocoding.
    """

    try:
        user_data = yield UserData.lookup(client, origin)
    except UserData.DoesNotExist:
        client.message(target, "{origin}: You need to be authenticated to set your location.".format(
            origin=origin,
        ))
        return

    r = requests.get(
        "https://maps.googleapis.com/maps/api/geocode/json",
        params={
            "address": place,
            "sensor": "false"
        }
    ).json()

    results = r.get("results", [])

    if not results:
        client.message(target, "{origin}: Can't find where \"{place}\" is.".format(
            origin=origin,
            place=place
        ))
        return


    if len(results) > 1:
        client.message(target, "{origin}: Please be more specific than \"{place}\".".format(
            origin=origin,
            place=place
        ))
        return

    result, = results

    user_data["location"] = result["geometry"]["location"]

    client.message(target, "{origin}: Okay, set your location to {formatted_address} ({lat:.10}, {lng:.10}).".format(
        origin=origin,
        formatted_address=result["formatted_address"],
        lat=result["geometry"]["location"]["lat"],
        lng=result["geometry"]["location"]["lng"]
    ))
