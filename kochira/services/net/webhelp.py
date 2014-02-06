"""
Interactive web help.

This service starts a web server to enable interactive help for all services.

Configuration Options
=====================

``port``
  Port to run the web help on, e.g. ``8080``.

``address`` (optional)
  Address to bind the HTTP server to.

``url``
  Base URL for the web help, e.g. ``http://example.com:8000``.

Commands
========

Help
----

::

    $bot: help
    $bot: help me!
    !help
    !commands

Links the user to the web help service.
"""

from kochira.service import Service
import os

from docutils.core import publish_parts
from tornado.web import RequestHandler, Application, HTTPError
from tornado.httpserver import HTTPServer

service = Service(__name__, __doc__)


class RequestHandler(RequestHandler):
    def render(self, name, **kwargs):
        services = [service for service, _ in self.application.bot.services.values()]
        services.sort(key=lambda s: s.name)

        kwargs.setdefault("service", None)

        return super().render(name,
                              bot=self.application.bot,
                              services=services,
                              rst=lambda s, **kw: publish_parts(s, writer_name="html", **kw)["fragment"],
                              **kwargs)


class IndexHandler(RequestHandler):
    def get(self):
        self.render("index.html")


class ServiceInfoHandler(RequestHandler):
    def get(self, service_name):
        try:
            service, _ = self.application.bot.services[service_name]
        except KeyError:
            raise HTTPError(404)
        else:
            self.render("service.html", service=service)


base_path = os.path.join(os.path.dirname(__file__), "webhelp")


@service.setup
def setup_webhelp(bot):
    config = service.config_for(bot)
    storage = service.storage_for(bot)

    storage.application = Application([
        (r"/", IndexHandler),
        (r"/services/(.*)", ServiceInfoHandler)
    ],
        template_path=os.path.join(base_path, "templates"),
        static_path=os.path.join(base_path, "static"),
        autoreload=False,
        compiled_template_cache=False
    )
    storage.application.bot = bot

    @bot.io_loop.add_callback
    def _callback():
        storage.http_server = HTTPServer(storage.application,
                                         io_loop=bot.io_loop)
        storage.http_server.listen(config["port"], config.get("address"))
        service.logger.info("webhelp ready")


@service.shutdown
def shutdown_webhelp(bot):
    storage = service.storage_for(bot)

    @bot.io_loop.add_callback
    def _callback():
        storage.http_server.stop()
        service.logger.info("webhelp stopped")


@service.command(r"!commands")
@service.command(r"!help")
@service.command(r"help(?: me)?!?$", mention=True)
def help(client, target, origin):
    config = service.config_for(client.bot)

    client.message(target, "{origin}: My help is available at {url}".format(
        origin=origin,
        url=config["url"]
    ))
