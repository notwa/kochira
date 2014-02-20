"""
Automatic and manual updater.

Allows the update command to be issued to update, and also installs a
post-receive web hook if the web server is loaded.

If the post-receive web hook is enabled, the post-receive hook is available at
http://mykochira/updater/?key=post_receive_key
"""

import subprocess

from kochira import config
from kochira.auth import requires_permission
from kochira.service import Service, Config, HookContext

from tornado.web import Application, RequestHandler, asynchronous, HTTPError

service = Service(__name__, __doc__)


@service.config
class Config(Config):
    remote = config.Field(doc="Remote to pull updates from.",
                          default="origin")
    branch = config.Field(doc="Branch to pull updates from.",
                          default="master")
    post_receive_key = config.Field(doc="Enable the post-receive hook if set. This is the ``key=<key>`` query argument.",
                                    default=None)
    announce = config.Field(doc="Whether or not to announce. Set this on a per-channel basis.", default=False)


class UpdateError(Exception):
    pass


def rev_parse(rev):
    p = subprocess.Popen(["git", "rev-parse", rev], stdout=subprocess.PIPE)
    commit_hash, _ = p.communicate()
    commit_hash = commit_hash.decode("utf-8").strip()

    if p.returncode != 0:
        raise UpdateError("git rev-parse failed")

    return commit_hash


def get_log(from_rev, to_rev):
    p = subprocess.Popen(["git", "log", "--graph", "--abbrev-commit",
                          "--date=relative", "--format=%h - (%ar) %s - %an",
                          from_rev + ".." + to_rev], stdout=subprocess.PIPE)

    out, _ = p.communicate()

    if p.returncode != 0:
        raise UpdateError("git log failed")

    return reversed([line for line in out.decode("utf-8").rstrip("\n").split("\n")
                     if line])


def do_update(remote, branch):
    p = subprocess.Popen(["git", "pull", remote, branch],
                         stdout=subprocess.PIPE)
    out, _ = p.communicate()

    if p.returncode != 0:
        raise UpdateError("git pull failed")

    return out.decode("utf-8").strip() != "Already up-to-date."


@service.command(r"(?:windows )?update(?:s)?!?$", mention=True, allow_private=True)
@requires_permission("admin")
def update(ctx):
    """
    Update.

    Update the bot by pulling from the latest Git master.
    """

    ctx.respond(ctx._("Checking for updates..."))

    try:
        head = rev_parse("HEAD")

        if not do_update(ctx.config.remote, ctx.config.branch):
            ctx.respond(ctx._("No updates."))
            return

        for line in get_log(head, "HEAD"):
            ctx.respond(line)
    except UpdateError as e:
        ctx.respond(ctx._("Update failed! {error}").format(error=e))
    else:
        ctx.respond(ctx._("Update finished!"))


class PostReceiveHandler(RequestHandler):
    @asynchronous
    def post(self):
        if self.get_query_argument("key") != self.application.ctx.config.post_receive_key:
            raise HTTPError(403)

        def _callback(future):
            if future.exception() is not None:
                self.send_error(500)
                raise future.exception()
            self.finish()

            for client_name, client in self.application.ctx.bot.clients.items():
                for channel in client.channels:
                    c_ctx = HookContext(service, self.application.ctx.bot, client.name, channel)

                    if not c_ctx.config.announce:
                        continue

                    for line in get_log(head, "HEAD"):
                        client.notice(channel, self.application.ctx._("Update! {line}").format(
                            line=line
                        ))

        head = rev_parse("HEAD")

        self.application.ctx.bot.executor.submit(do_update,
                                                 self.application.ctx.config.remote,
                                                 self.application.ctx.config.branch) \
            .add_done_callback(_callback)


def make_application(settings):
    return Application([
        (r"/", PostReceiveHandler)
    ], **settings)


@service.hook("services.net.webserver")
def webserver_config(ctx):
    if ctx.config.post_receive_key is None:
        return None

    return {
        "name": "updater",
        "title": None,
        "application_factory": make_application
    }
