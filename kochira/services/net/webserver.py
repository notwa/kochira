"""
Web server.

This service starts a web server to allow services to run things on a web
server.

Configuration Options
=====================

``port``
  Port to run the web help on, e.g. ``8080``.

``address`` (optional)
  Address to bind the HTTP server to.

Commands
========
None.
"""

from kochira.service import Service
import os

from tornado.web import RequestHandler, Application, UIModule, HTTPError
from tornado.httpserver import HTTPServer, HTTPRequest

service = Service(__name__, __doc__)


class MainHandler(RequestHandler):
    def _get_application_factory(self, name):
        for conf in self.application.settings["get_application_confs"]():
            if conf["name"] == name:
                return conf["application_factory"]

        raise HTTPError(404)

    def _run_request(self, name, url):
        application = self._get_application_factory(name)(self.settings)
        application.name = name
        application(HTTPRequest(self.request.method, "/" + url,
                                self.request.version, self.request.headers,
                                self.request.body, self.request.remote_ip,
                                self.request.protocol, self.request.host,
                                self.request.files, self.request.connection))
        self._handled = True

    def finish(self, chunk=None):
        if getattr(self, "_handled", False):
            return

        return super().finish(chunk)

    get = _run_request
    head = _run_request
    post = _run_request
    delete = _run_request
    patch = _run_request
    put = _run_request
    options = _run_request


class IndexHandler(RequestHandler):
    def get(self):
        self.render("index.html",
                    networks=sorted(self.application.settings["bot"].networks.items()))


class NavBarModule(UIModule):
    def render(self):
        get_application_confs = self.handler.application.settings["get_application_confs"]
        return self.render_string("_modules/navbar.html",
                                  name=self.handler.application.name,
                                  factories=sorted(get_application_confs()))

base_path = os.path.join(os.path.dirname(__file__), "webserver")


@service.setup
def setup_webserver(bot):
    config = service.config_for(bot)
    storage = service.storage_for(bot)

    def get_application_confs():
        for hook in bot.get_hooks("services.net.webserver"):
            yield hook(bot)

    storage.application = Application([
        (r"/", IndexHandler),
        (r"/(\S+)/(.*)", MainHandler)
    ],
        template_path=os.path.join(base_path, "templates"),
        static_path=os.path.join(base_path, "static"),
        autoreload=False,
        compiled_template_cache=False,
        bot=bot,
        get_application_confs=get_application_confs,
        ui_modules={"NavBar": NavBarModule}
    )
    storage.application.name = None

    @bot.io_loop.add_callback
    def _callback():
        storage.http_server = HTTPServer(storage.application,
                                         io_loop=bot.io_loop)
        storage.http_server.listen(config["port"], config.get("address"))
        service.logger.info("web server ready")


@service.shutdown
def shutdown_webserver(bot):
    storage = service.storage_for(bot)

    @bot.io_loop.add_callback
    def _callback():
        storage.http_server.stop()
        service.logger.info("web server stopped")
