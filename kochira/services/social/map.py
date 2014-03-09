"""
Map.

Display a map of user-provided location information.
"""

from kochira.service import Service
from kochira.userdata import UserDataKVPair

from tornado.web import RequestHandler, Application

service = Service(__name__, __doc__)


@service.command(r"!map")
@service.command(r"where is everyone\??", mention=True, priority=1)
def show_map(ctx):
    """
    Show map.

    Links the user to the web map, if available.
    """

    if "kochira.services.net.webserver" not in ctx.bot.services:
        ctx.respond(ctx._("Map currently unavailable."))
    else:
        ctx.respond(ctx._("The map is available at {url}").format(
            url=ctx.bot.config.services["kochira.services.net.webserver"].base_url.rstrip("/") + "/map/"
        ))


class IndexHandler(RequestHandler):
    def get(self):
        self.render("map/index.html",
                    locations=[{
                        "account": location.account,
                        "network": location.network,
                        "formattedAddress": location.value["formatted_address"],
                        "lat": location.value["lat"],
                        "lng": location.value["lng"]
                    } for location in UserDataKVPair.select().where(
                        UserDataKVPair.key == "location")])


def make_application(settings):
    return Application([
        (r"/", IndexHandler)
    ], **settings)


@service.hook("services.net.webserver")
def webserver_config(ctx):
    return {
        "name": "map",
        "title": "Map",
        "application_factory": make_application
    }
