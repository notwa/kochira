"""
Help and documentation.

This service displays help information on the web server.
"""

import itertools
import re

from kochira import config
from kochira.service import Service, Config
from docutils.core import publish_parts
from tornado.web import RequestHandler, Application, HTTPError, UIModule

service = Service(__name__, __doc__)


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
@service.command(r"!help(?: (?P<trigger>.+))?")
@service.command(r"help(?: me)?!?$", mention=True)
def help(ctx, trigger=None):
    """
    Help.

    Links the user to the web help service, if available.
    """

    if "kochira.services.net.webserver" not in ctx.bot.services:
        ctx.respond(ctx._("Help currently unavailable."))
    else:
        if trigger is not None:
            matches = []

            for service_name, binding in ctx.bot.services.items():
                for command in binding.service.commands:
                    for pattern, _ in command.patterns:
                        if re.match(pattern, trigger) is not None:
                            matches.append((command, service_name))

            if matches:
                command, service_name = next(iter(matches))
                ctx.respond(ctx._("Help for that command is available at {url}").format(
                    url=ctx.bot.config.services["kochira.services.net.webserver"].base_url.rstrip("/") + "/help/" + service_name + "#" + command.__name__
                ))
            else:
                ctx.respond(ctx._("No help available for this command."))
        else:
            ctx.respond(ctx._("My help is available at {url}").format(
                url=ctx.bot.config.services["kochira.services.net.webserver"].base_url.rstrip("/") + "/help/"
            ))


@service.command(r"!source")
@service.command(r"source", mention=True)
@service.command(r"repo", mention=True)
@service.command(r"github", mention=True)
def show_source(ctx):
    """
    Show source.

    Links the user to the source code repository.
    """
    ctx.respond(ctx._("My source code is at: https://github.com/rfw/kochira"))



@service.command(r"!bugs")
@service.command(r"report (?:a )?bug", mention=True)
@service.command(r"bugs", mention=True)
@service.command(r"u stink", mention=True)
def bug_report(ctx):
    """
    Bug report.

    Links the user to the bug report URL.
    """
    ctx.respond(ctx._("Found a bug? Report it! https://github.com/rfw/kochira/issues"))

