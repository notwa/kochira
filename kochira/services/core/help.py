"""
Help and documentation.

This service displays help information on the web server.
"""

from kochira import config
from kochira.service import Service, Config
from docutils.core import publish_parts
from tornado.web import RequestHandler, Application, HTTPError, UIModule

service = Service(__name__, __doc__)

@service.config
class Config(Config):
    url = config.Field(doc="Base URL for the help documentation, e.g. ``http://example.com:8000/help``.")


def rst(s, **kw):
    return publish_parts(s, writer_name="html", **kw)["fragment"]


def trim_docstring(docstring):
    inf = float("inf")

    if not docstring:
        return ''
    # Convert tabs to spaces (following the normal Python rules)
    # and split into a list of lines:
    lines = docstring.expandtabs().splitlines()
    # Determine minimum indentation (first line doesn't count):
    indent = inf
    for line in lines[1:]:
        stripped = line.lstrip()
        if stripped:
            indent = min(indent, len(line) - len(stripped))
    # Remove indentation (first line is special):
    trimmed = [lines[0].strip()]
    if indent < inf:
        for line in lines[1:]:
            trimmed.append(line[indent:].rstrip())
    # Strip off trailing and leading blank lines:
    while trimmed and not trimmed[-1]:
        trimmed.pop()
    while trimmed and not trimmed[0]:
        trimmed.pop(0)
    # Return a single string:
    return '\n'.join(trimmed)


def _get_doc_parts(doc):
    if doc is None:
        return None
    return trim_docstring(doc).strip().split("\n\n")


def get_short_doc(doc):
    parts = _get_doc_parts(doc)
    if parts is None:
        return None

    return parts[0]


def get_long_doc(doc):
    parts = _get_doc_parts(doc)
    if parts is None:
        return None

    return "\n\n".join(parts[1:])


class RequestHandler(RequestHandler):
    def render(self, name, **kwargs):
        return super().render(name,
                              rst=rst,
                              trim_docstring=trim_docstring,
                              get_long_doc=get_long_doc,
                              get_short_doc=get_short_doc,
                              **kwargs)


class IndexHandler(RequestHandler):
    def get(self):
        services = [bound.service for bound in self.application.ctx.bot.services.values()]
        services.sort(key=lambda s: s.name)

        self.render("help/index.html", services=services,
                    bot_config=self.application.ctx.bot.config_class)


class ServiceHelpHandler(RequestHandler):
    def get(self, service_name):
        try:
            service = self.application.ctx.bot.services[service_name].service
        except KeyError:
            raise HTTPError(404)
        self.render("help/service.html", service=service)


class ConfigModule(UIModule):
    def render(self, cfg):
        return self.render_string("help/_modules/config.html",
                                  config=cfg, ConfigType=config.Config,
                                  rst=rst)


def make_application(settings):
    settings = settings.copy()
    settings["ui_modules"]["Config"] = ConfigModule

    return Application([
        (r"/", IndexHandler),
        (r"/(.*)", ServiceHelpHandler)
    ], **settings)


@service.hook("services.net.webserver")
def webserver_config(ctx):
    return {
        "name": "help",
        "title": "Help",
        "menu_order": 9999,
        "application_factory": make_application
    }


@service.command(r"!commands")
@service.command(r"!help")
@service.command(r"help(?: me)?!?$", mention=True)
def help(ctx):
    """
    Help.

    Links the user to the web help service, if available.
    """

    if "kochira.services.net.webserver" not in ctx.bot.services:
        ctx.respond(ctx._("Help currently unavailable."))
    else:
        ctx.respond(ctx._("My help is available at {url}").format(
            url=ctx.config.url
        ))
