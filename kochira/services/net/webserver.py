"""
Web server.

This service starts a web server to allow services to run things on a web
server.
"""

from docutils.core import publish_parts

from kochira import config
from kochira.service import Service, Config, HookContext

import copy
import os
import subprocess

from tornado.web import RequestHandler, Application, UIModule, HTTPError
from tornado.httpserver import HTTPServer, HTTPRequest

from urllib.parse import urlparse

service = Service(__name__, __doc__)


@service.config
class Config(Config):
    port = config.Field(doc="Port to run the web server on.", default=8080)
    address = config.Field(doc="Address to bind the HTTP server to.", default="0.0.0.0")
    title = config.Field(doc="Title for the web site.", default="Kochira")
    motd = config.Field(doc="MOTD for the web site, formatted in reStructuredText.", default="(no message of the day)")
    base_url = config.Field(doc="Base URL for the web server.")


def _get_application_confs(bot):
    for hook in bot.get_hooks("services.net.webserver"):
        conf = hook(HookContext(hook.service, bot))

        if conf:
            yield hook.service, conf


class MainHandler(RequestHandler):
    def _get_application_factory(self, name):
        for service, conf in _get_application_confs(self.application._ctx.bot):
            if conf["name"] == name:
                return service, conf["application_factory"]

        raise HTTPError(404)

    def _run_request(self, name):
        service, application_factory = self._get_application_factory(name)

        application = application_factory(self.settings)
        application._ctx = self.application._ctx
        application.ctx = HookContext(service, self.application._ctx.bot)
        application.name = name

        path = self.request.path[len(name) + 1:]

        request = copy.copy(self.request)
        request.path = path

        application(request)
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
                    motd=publish_parts(self.application._ctx.config.motd,
                                       writer_name="html",
                                       settings_overrides={"initial_header_level": 2})["fragment"],
                    clients=sorted(self.application._ctx.bot.clients.items()))


class NotFoundHandler(RequestHandler):
    def get(self):
        self.set_status(404)
        self.render("404.html")


class TitleModule(UIModule):
    def render(self):
        return self.render_string("_modules/title.html",
                                  title=self.handler.application._ctx.config.title)


class NavBarModule(UIModule):
    def render(self):
        return self.render_string("_modules/navbar.html",
                                  title=self.handler.application._ctx.config.title,
                                  name=self.handler.application.name,
                                  confs=[conf for _, conf in _get_application_confs(self.handler.application._ctx.bot)])


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

            p = subprocess.Popen(["git", "config", "--get", "remote.origin.url"], stdout=subprocess.PIPE)
            remote, _ = p.communicate()

            if p.returncode != 0:
                remote = None
            else:
                remote = urlparse(remote.strip().decode("utf-8"))

                if not remote.scheme.startswith("http"):
                    remote = None
                elif remote.username and remote.password:
                    remote = urlparse(remote.geturl().replace("{username}:{password}@".format(
                        username=remote.username,
                        password=remote.password
                    ), ""))

        return self.render_string("_modules/footer.html",
                                  revision=revision,
                                  dirty=dirty,
                                  remote=remote)


base_path = os.path.join(os.path.dirname(__file__), "webserver")


@service.setup
def setup_webserver(ctx):
    ctx.storage.application = Application([
        (r"/", IndexHandler),
        (r"/(\S+)/.*", MainHandler),
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
    ctx.storage.application._ctx = HookContext(service, ctx.bot)
    ctx.storage.application.name = None

    @ctx.bot.event_loop.schedule
    def _callback():
        ctx.storage.http_server = HTTPServer(ctx.storage.application,
                                             io_loop=ctx.bot.event_loop.io_loop)
        ctx.storage.http_server.listen(ctx.config.port, ctx.config.address)
        service.logger.info("web server ready")


@service.shutdown
def shutdown_webserver(ctx):
    # we have to do this because the service will be unloaded on the next
    # scheduler tick
    storage = ctx.storage

    @ctx.bot.event_loop.schedule
    def _callback():
        storage.http_server.stop()
        service.logger.info("web server stopped")
