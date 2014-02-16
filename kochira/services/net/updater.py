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
from kochira.service import Service, Config

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

    return reversed(line for line in out.decode("utf-8").rstrip("\n").split("\n")
                    if line)


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
    """
    Update.

    Update the bot by pulling from the latest Git master.
    """

    config = service.config_for(client.bot)

    client.message(target, "Checking for updates...")

    try:
        head = rev_parse("HEAD")

        if not do_update(config.remote, config.branch):
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

        if self.get_query_argument("key") != config.post_receive_key:
            raise HTTPError(403)

        def _callback(future):
            if future.exception() is not None:
                self.send_error(500)
                raise future.exception()
            self.finish()

            for client_name, client in self.application.bot.clients.items():
                for channel in client.channels:
                    config = service.config_for(self.application.bot,
                                                client_name, channel)

                    if not config.announce:
                        continue

                    for line in get_log(head, "HEAD"):
                        client.notice(channel, "Update! {}".format(line))

        head = rev_parse("HEAD")

        self.application.bot.executor.submit(do_update,
                                             config.remote,
                                             config.branch) \
            .add_done_callback(_callback)


def make_application(settings):
    return Application([
        (r"/", PostReceiveHandler)
    ], **settings)


@service.hook("services.net.webserver")
def webserver_config(bot):
    config = service.config_for(bot)

    if config.post_receive_key is None:
        return None

    return {
        "name": "updater",
        "title": None,
        "application_factory": make_application
    }
