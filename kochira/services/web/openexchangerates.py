"""
Open Exchange Rates currency conversion.

Convert between currencies using Open Exchange Rates.
"""

import requests
import pycountry
import time

from kochira import config
from kochira.service import Service, background, Config, coroutine
from kochira.userdata import UserData

service = Service(__name__, __doc__)


@service.config
class Config(Config):
    app_id = config.Field(doc="Open Exchange Rates App ID.")


@service.setup
def initialize_storage(ctx):
    ctx.storage.last_update = 0


def _update_currencies(app_id, storage):
    now = time.time()

    if storage.last_update + 60 * 60 <= now:
        req = requests.get(
            "https://openexchangerates.org/api/latest.json",
            params={
                "app_id": app_id,
                "base": "USD"
            }
        )
        req.raise_for_status()

        storage.rates = req.json()["rates"]
        storage.last_update = now


@service.command(r"convert (?P<amount>\d+(?:\.\d*)?)(?: ?(?P<from_currency>\S+))?(?: to (?P<to_currency>\S+))?", mention=True)
@background
@coroutine
def convert(ctx, amount: float, from_currency=None, to_currency=None):
    """
    Convert.

    Convert between currencies. Defaults to geolocated currencies.
    """
    _update_currencies(ctx.config.app_id, ctx.storage)

    if from_currency is None and to_currency is None:
        ctx.respond(ctx._("You haven't specified a currency pair."))
        return

    if from_currency is None or to_currency is None:
        try:
            geocode = ctx.provider_for("geocode")
        except KeyError:
            ctx.respond(ctx._("Sorry, I don't have a geocode provider loaded, and you haven't specified both currencies."))
            return

        user_data = yield ctx.bot.defer_from_thread(UserData.lookup_default, ctx.client, ctx.origin)

        if "location" not in user_data:
            ctx.respond(ctx._("You don't have location data set."))
            return

        result = (yield geocode(ctx.origin))[0]

        country = pycountry.countries.get(
            alpha2=[component["short_name"] for component in result["address_components"]
                    if "country" in component["types"]][0]
        )

        currency = pycountry.currencies.get(numeric=country.numeric)

        if from_currency is None:
            from_currency = currency.letter

        if to_currency is None:
            to_currency = currency.letter

    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    for currency in [from_currency, to_currency]:
        if currency not in ctx.storage.rates:
            ctx.respond(ctx._("I don't know the exchange rate for {currency}.").format(
                currency=currency
            ))
            return

    try:
        from_currency_name = pycountry.currencies.get(letter=from_currency_name).name
    except KeyError:
        from_currency_name = "unknown"

    try:
        to_currency_name = pycountry.currencies.get(letter=to_currency_name).name
    except KeyError:
        to_currency_name = "unknown"

    den = ctx.storage.rates[from_currency]
    num = ctx.storage.rates[to_currency]

    converted = amount * num / den

    ctx.respond(ctx._("{amount:.4f} {from_currency} ({from_currency_name}) = {converted:.4f} {to_currency} ({to_currency_name})").format(
        amount=amount,
        from_currency=from_currency,
        from_currency_name=from_currency_name,
        converted=converted,
        to_currency=to_currency,
        to_currency_name=to_currency_name
    ))

