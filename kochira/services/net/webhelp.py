"""
Interactive web help.

This service starts a web server to enable interactive help for all services.

Configuration Options
=====================

``port``
  Port to run the web help on, e.g. ``8080``.

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
import threading

from docutils.core import publish_parts
from tornado import ioloop
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

class IOLoopThread(threading.Thread):
    daemon = True

    def __init__(self):
        self.event = threading.Event()
        self.stop_event = threading.Event()
        super().__init__()

    def run(self):
        try:
            self.io_loop = ioloop.IOLoop()
        finally:
            self.event.set()

        self.io_loop.start()
        self.io_loop.close(all_fds=True)
        self.stop_event.set()

    def stop(self):
        @self.io_loop.add_callback
        def _callback():
            self.io_loop.stop()
        self.stop_event.wait()

@service.setup
def setup_webhelp(bot):
    config = service.config_for(bot)
    storage = service.storage_for(bot)

    storage.ioloop_thread = IOLoopThread()
    storage.ioloop_thread.start()
    storage.ioloop_thread.event.wait()

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

    @storage.ioloop_thread.io_loop.add_callback
    def _callback():
        storage.http_server = HTTPServer(
            storage.application,
            io_loop=storage.ioloop_thread.io_loop
        )

        storage.http_server.listen(config["port"], config.get("address"))


@service.shutdown
def shutdown_webhelp(bot):
    storage = service.storage_for(bot)
    storage.ioloop_thread.stop()


@service.command(r"!commands")
@service.command(r"!help")
@service.command(r"help(?: me)?!?$", mention=True)
def help(client, target, origin):
    config = service.config_for(client.bot)

    client.message(target, "{origin}: My help is available at {url}".format(
        origin=origin,
        url=config["url"]
    ))
