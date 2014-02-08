"""
Automatic and manual updater.

Allows the update command to be issued to update, and also installs a
post-receive web hook if the web server is loaded.

Configuration Options
=====================

``remote`` (optional)
  Remote to pull updates from. Defaults to ``origin``.

``branch`` (optional)
  Branch to pull updates from. Defaults to ``master``.

``post_receive_key`` (optional)
  Enable the post-receive hook if set. This is the ``key=<key>`` query
  argument.

Commands
========

Update
------

::

    $bot: update
    $bot: windows updates!

**Requires permission:** update

Update the bot by pulling from the latest Git master.
"""

import subprocess

from kochira.auth import requires_permission
from kochira.service import Service

from tornado.web import Application, RequestHandler, asynchronous, HTTPError

service = Service(__name__, __doc__)


def do_update(remote, branch):
    p = subprocess.Popen(["git", "pull", remote, branch],
                         stdout=subprocess.PIPE)
    out, _ = p.communicate()

    if p.returncode != 0:
        return None

    return out.decode("utf-8").strip()


@service.command(r"(?:windows )?update(?:s)?!?$", mention=True, allow_private=True)
@requires_permission("admin")
def update(client, target, origin):
    config = service.config_for(client.bot)

    client.message(target, "Checking for updates...")

    p = subprocess.Popen(["git", "rev-parse", "HEAD"], stdout=subprocess.PIPE)
    head, _ = p.communicate()
    head = head.decode("utf-8").strip()

    if p.returncode != 0:
        client.message(target, "Update failed!")
        return

    out = do_update(config.get("remote", "origin"),
                    config.get("branch", "master"))

    if out is None:
        client.message(target, "Update failed!")
        return

    if out == "Already up-to-date.":
        client.message(target, "No updates.")
        return

    p = subprocess.Popen(["git", "log", "--graph", "--abbrev-commit",
                          "--date=relative", "--format=%h - (%ar) %s - %an",
                          head + "..HEAD"], stdout=subprocess.PIPE)

    out, _ = p.communicate()

    if p.returncode != 0:
        client.message(target, "Update failed!")
        return

    for line in out.decode("utf-8").rstrip("\n").split("\n"):
        client.message(target, line)

    client.message(target, "Update finished!")


class PostReceiveHandler(RequestHandler):
    def _callback(self, future):
        if future.exception() is not None:
            raise future.exception()
        self.finish()

    @asynchronous
    def post(self):
        config = service.config_for(self.application.bot)

        if self.get_query_argument("key") != config["post_receive_key"]:
            raise HTTPError(403)

        self.application.bot.executor.submit(do_update) \
            .add_done_callback(self._callback)


def make_application(settings):
    return Application([
        (r"/", PostReceiveHandler)
    ], **settings)


@service.hook("services.net.webserver")
def webserver_config(bot):
    config = service.config_for(bot)

    if not config.get("post_receive_key"):
        return None

    return {
        "name": "updater",
        "title": None,
        "application_factory": make_application
    }

