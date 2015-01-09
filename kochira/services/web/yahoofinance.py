"""
Yahoo! Finance.

Get stock price information.
"""

import csv
import requests
import io

from kochira import config
from kochira.service import Service, background, Config, coroutine
from kochira.userdata import UserData

service = Service(__name__, __doc__)


@service.command(r"!stock (?P<symbol>\S+)")
@service.command(r"stock price for (?P<symbol>\S+)", mention=True)
@background
@coroutine
def stock_price(ctx, symbol):
    """
    Stock price.

    Get the stock price for a given symbol.
    """

    (symbol, exchange, name, last_trade_price, last_trade_time, change, change_pct), = csv.reader(
        io.StringIO(requests.get(
            "http://download.finance.yahoo.com/d/quotes.csv",
            params={"s": symbol, "f": "sxnl1t1c1p2"}).text),
        delimiter=",", quotechar="\"")

    ctx.respond(ctx._("The last trading price at {last_trade_time} for {name} ({exchange}: {symbol}) is {last_trade_price} ({change} ({change_pct}))").format(
        last_trade_time=last_trade_time,
        last_trade_price=last_trade_price,
        name=name,
        exchange=exchange,
        symbol=symbol
        change=change,
        change_pct=change_pct))
