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

``announce`` (optional)
  Channels to announce updates on.

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

    return out.decode("utf-8").rstrip("\n").split("\n")


def do_update(remote, branch):
    p = subprocess.Popen(["git", "pull", remote, branch],
                         stdout=subprocess.PIPE)
    out, _ = p.communicate()

    if p.returncode != 0:
        raise UpdateError("git pull failed")

    return out.decode("utf-8").strip() != "Already up-to-date."


@service.command(r"(?:windows )?update(?:s)?!?$", mention=True, allow_private=True)
@requires_permission("admin")
def update(client, target, origin):
    config = service.config_for(client.bot)

    client.message(target, "Checking for updates...")

    try:
        head = rev_parse("HEAD")

        if not do_update(config.get("remote", "origin"),
                         config.get("branch", "master")):
            client.message(target, "No updates.")
            return

        for line in get_log(head, "HEAD"):
            client.message(target, line)
    except UpdateError as e:
        client.message(target, "Update failed! " + str(e))
    else:
        client.message(target, "Update finished!")


class PostReceiveHandler(RequestHandler):
    @asynchronous
    def post(self):
        config = service.config_for(self.application.bot)

        if self.get_query_argument("key") != config["post_receive_key"]:
            raise HTTPError(403)

        def _callback(future):
            if future.exception() is not None:
                self.send_error(500)
                raise future.exception()
            self.finish()

            for announce in config.get("announce", []):
                for line in get_log(head, "HEAD"):
                    self.application.bot.networks[announce["network"]].message(
                        announce["channel"],
                        "Update! {}".format(line)
                    )

        head = rev_parse("HEAD")

        self.application.bot.executor.submit(do_update,
                                             config.get("remote", "origin"),
                                             config.get("branch", "master")) \
            .add_done_callback(_callback)


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

