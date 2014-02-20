"""
Weather Underground forecast.

Get weather data from Weather Underground
"""

import requests

from kochira import config
from kochira.service import Service, background, Config, coroutine
from kochira.userdata import UserData

service = Service(__name__, __doc__)


@service.config
class Config(Config):
    api_key = config.Field(doc="Weather Underground API key.")


def geocode(address):
    return requests.get(
        "https://maps.googleapis.com/maps/api/geocode/json",
        params={
            "address": address,
            "sensor": "false"
        }
    ).json().get("results", [])


@service.command(r"!weather(?: (?P<where>.+))?")
@service.command(r"weather(?: (?:for|in) (?P<where>.+))?", mention=True)
@background
@coroutine
def weather(ctx, where=None):
    """
    Weather.

    Get the weather for a location.
    """
    if where is None:
        try:
            user_data = yield ctx.bot.defer_from_thread(UserData.lookup, ctx.client, ctx.origin)
        except UserData.DoesNotExist:
            user_data = {}

        if "location" not in user_data:
            ctx.respond(ctx._("I don't have location data for you."))
            return
        location = user_data["location"]
    else:
        user_data = yield ctx.bot.defer_from_thread(UserData.lookup_default, ctx.client, where)
        location = user_data.get("location")

        if location is None:
            geocoded = geocode(where)

            if not geocoded:
                ctx.respond(ctx._("I don't know where \"{where}\" is.").format(where=where))
                return

            location = geocoded[0]["geometry"]["location"]

    r = requests.get("http://api.wunderground.com/api/{api_key}/conditions/q/{lat},{lng}.json".format(
        api_key=ctx.config.api_key,
        **location
    )).json()

    if "error" in r:
        ctx.respond(ctx._("Sorry, there was an error: {type}: {description}").format(
            **r["error"]
        ))
        return

    if "current_observation" not in r:
        ctx.respond(ctx._("Couldn't find weather for \"{where}\".").format(where=where))
        return

    observation = r["current_observation"]

    place = observation["display_location"]["full"]

    if observation["display_location"]["country"].upper() == "US":
        def _unitize(nonus, us):
            return us
    else:
        def _unitize(nonus, us):
            return nonus

    temp = observation["temp_" + _unitize("c", "f")]
    feelslike = observation["feelslike_" + _unitize("c", "f")]
    wind = observation["wind_" + _unitize("kph", "mph")]
    wind_dir = observation["wind_dir"]
    humidity = observation["relative_humidity"]
    precip = observation["precip_today_" + _unitize("metric", "in")]
    weather = observation["weather"]

    ctx.respond(ctx._("Today's weather for {place} is: {weather}, {temp} °{cf} (feels like {feelslike} °{cf}), wind from {wind_dir} at {wind} {kphmph}, {humidity} humidity, {precip} {mmin} precipitation").format(
        place=place,
        weather=weather,
        feelslike=feelslike,
        temp=temp,
        cf=_unitize("C", "F"),
        wind_dir=wind_dir,
        wind=wind,
        kphmph=_unitize("km/h", "mph"),
        humidity=humidity,
        precip=precip,
        mmin=_unitize("mm", "in")
    ))
