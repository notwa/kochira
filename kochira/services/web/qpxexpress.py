"""
QPX Express flight search.

Find flights using ITA Software's flight search.
"""

from kochira import config
from kochira.service import Service, background, Config

import ccy
import dateutil.parser
import json
import re
import requests
import urllib.parse

service = Service(__name__, __doc__)


@service.config
class Config(Config):
    api_key = config.Field(doc="Google API key.")


SLICE_SPEC_EXPR = re.compile(r"from (?P<origin>.+?) to (?P<destination>.+?) on (?P<date>.+?)$")


@service.command(r"flights(?: for (?P<num_adults>\d+)(?: adults?)?)? (?P<slice_specs>.*)", mention=True)
@background
def flight_search(ctx, slice_specs, num_adults: int=1):
    """
    Search for flights.

    Find flights for a given set of journeys, e.g. "flights from SEA to SFO on
    mar 3, SFO to SEA on apr 3".
    """
    slices = []

    for slice_spec in slice_specs.split(","):
        slice_spec = slice_spec.strip()
        match = SLICE_SPEC_EXPR.match(slice_spec)

        if match is None:
            ctx.respond(
                ctx._("Couldn't figure out what you wanted. Make sure flights are in the format \"flights from <origin> to <destination> on <date>\"."))
            return

        slices.append({
            "origin": match.group("origin"),
            "destination": match.group("destination"),
            "date": dateutil.parser.parse(match.group("date")).strftime("%Y-%m-%d")
        })

    resp = requests.post(
        "https://www.googleapis.com/qpxExpress/v1/trips/search",
        params={
            "key": ctx.config.api_key
        },
        headers={
            "Content-Type": "application/json"
        },
        data=json.dumps({
            "request": {
                "passengers": {
                    "adultCount": num_adults or 1
                },
                "slice": slices,
                "solutions": 5
            }
        })).json()

    if "error" in resp:
        ctx.respond(ctx._("Error while computing flights: {message}").format(message=resp["error"]["message"]))
        return

    trips = resp["trips"]
    data = trips["data"]
    options = trips["tripOption"]

    cities = {city["code"]: city for city in data["city"]}
    airports = {airport["code"]: airport for airport in data["airport"]}
    #carriers = {carrier["code"]: carrier for carrier in data["carrier"]}

    for airport in airports.values():
        airport["city"] = cities[airport["city"]]

    for option in options:
        price = option["saleTotal"]
        slices = option["slice"]

        last_departure_time = None
        slice_infos = []

        for slice in slices:
            segments = slice["segment"]
            segment_infos = []

            for segment in segments:
                legs = segment["leg"]

                for leg in legs:
                    departure_time = dateutil.parser.parse(leg["departureTime"])
                    arrival_time = dateutil.parser.parse(leg["arrivalTime"])

                    origin_airport = airports[leg["origin"]]
                    destination_airport = airports[leg["destination"]]

                    orig_time = departure_time.strftime("%H:%M")
                    if last_departure_time is None or departure_time.date() != last_departure_time.date():
                        orig_time = departure_time.strftime("%b %d") + ", " + orig_time

                    last_departure_time = departure_time

                    dest_time = arrival_time.strftime("%H:%M")
                    if departure_time.date() != arrival_time.date():
                        dest_time = arrival_time.strftime("%b %d") + ", " + dest_time

                    segment_infos.append(ctx._("{origin} ({departure}) -/{flight}/-> {destination} ({arrival})").format(
                        departure=orig_time,
                        origin=origin_airport["code"],
                        flight="{carrier}{number}".format(**segment["flight"]),
                        arrival=dest_time,
                        destination=destination_airport["code"]))

            slice_infos.append(", ".join(segment_infos))

    currency = ccy.currency(price[:3])

    ctx.respond(
        ctx._("For {symbol}{price}: {segments}").format(
            symbol=currency.symbol
            price=price[3:],
            segments=" | ".join(slice_infos)))
