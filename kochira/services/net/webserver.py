"""
Web server.

This service starts a web server to allow services to run things on a web
server.
"""

from docutils.core import publish_parts

from kochira import config
from kochira.service import Service
import os
import subprocess

from tornado.web import RequestHandler, Application, UIModule, HTTPError
from tornado.httpserver import HTTPServer, HTTPRequest

service = Service(__name__, __doc__)


@service.config
class Config(config.Config):
    port = config.Field(doc="Port to run the web server on.", default=8080)
    address = config.Field(doc="Address to bind the HTTP server to.", default="0.0.0.0")
    title = config.Field(doc="Title for the web site.", default="Kobun")
    motd = config.Field(doc="MOTD for the web site, formatted in reStructuredText.", default="(no message of the day)")


def _get_application_confs(bot):
    for hook in bot.get_hooks("services.net.webserver"):
        conf = hook(bot)

        if conf:
            yield conf


class MainHandler(RequestHandler):
    def _get_application_factory(self, name):
        for conf in _get_application_confs(self.application.bot):
            if conf["name"] == name:
                return conf["application_factory"]

        raise HTTPError(404)

    def _run_request(self, name, url):
        application = self._get_application_factory(name)(self.settings)
        application.name = name
        application.bot = self.application.bot

        uri = self.request.uri[len(name) + 1:]

        application(HTTPRequest(self.request.method, uri,
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
        config = service.config_for(self.application.bot)

        self.render("index.html",
                    motd=publish_parts(config.motd, writer_name="html", settings_overrides={"initial_header_level": 2})["fragment"],
                    networks=sorted(self.application.bot.networks.items()))

class NotFoundHandler(RequestHandler):
    def get(self):
        self.set_status(404)
        self.render("404.html")


class TitleModule(UIModule):
    def render(self):
        config = service.config_for(self.handler.application.bot)

        return self.render_string("_modules/title.html",
                                  title=config.title)

class NavBarModule(UIModule):
    def render(self):
        config = service.config_for(self.handler.application.bot)

        return self.render_string("_modules/navbar.html",
                                  title=config.title,
                                  name=self.handler.application.name,
                                  confs=_get_application_confs(self.handler.application.bot))


class FooterModule(UIModule):
    def render(self):
        p = subprocess.Popen(["git", "rev-parse", "HEAD"], stdout=subprocess.PIPE)
        revision, _ = p.communicate()

        dirty = False

        if p.returncode != 0:
            revision = None
        else:
            revision = revision.decode("utf-8").strip()[:8]

            p = subprocess.Popen(["git", "status", "--porcelain"], stdout=subprocess.PIPE)
            status, _ = p.communicate()

            if p.returncode == 0:
                if status.strip():
                    dirty = True

        return self.render_string("_modules/footer.html",
                                  revision=revision,
                                  dirty=dirty)


base_path = os.path.join(os.path.dirname(__file__), "webserver")


@service.setup
def setup_webserver(bot):
    config = service.config_for(bot)
    storage = service.storage_for(bot)

    storage.application = Application([
        (r"/", IndexHandler),
        (r"/(\S+)/(.*)", MainHandler),
        (r".*", NotFoundHandler)
    ],
        template_path=os.path.join(base_path, "templates"),
        static_path=os.path.join(base_path, "static"),
        autoreload=False,
        compiled_template_cache=False,
        ui_modules={
            "NavBar": NavBarModule,
            "Title": TitleModule,
            "Footer": FooterModule
        }
    )
    storage.application.bot = bot
    storage.application.name = None

    @bot.io_loop.add_callback
    def _callback():
        storage.http_server = HTTPServer(storage.application,
                                         io_loop=bot.io_loop)
        storage.http_server.listen(config.port, config.address)
        service.logger.info("web server ready")


@service.shutdown
def shutdown_webserver(bot):
    storage = service.storage_for(bot)

    @bot.io_loop.add_callback
    def _callback():
        storage.http_server.stop()
        service.logger.info("web server stopped")
