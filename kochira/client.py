import logging
from collections import deque
from pydle import Client

logger = logging.getLogger(__name__)


def make_hook(name):
    def _hook_function(self, *args, **kwargs):
        self.bot.run_hooks(name, self, *args, **kwargs)
    return _hook_function


class Client(Client):
    def __init__(self, bot, network, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.backlogs = {}
        self.bot = bot

        # set network name to whatever we have in our config
        self.network = network

    def on_connect(self):
        logger.info("Connected to IRC network: %s", self.network)
        super().on_connect()
        self.bot.run_hooks("connect", self)

    def message(self, target, message):
        super().message(target, message)
        self.bot.run_hooks("own_message", self, target, message)

    def on_channel_message(self, target, origin, message):
        backlog = self.backlogs.setdefault(target, deque([]))
        backlog.appendleft((origin, message))

        while len(backlog) > self.bot.config["core"].get("max_backlog", 10):
            backlog.pop()

        self.bot.run_hooks("channel_message", self, target, origin, message)

    def on_private_message(self, origin, message):
        backlog = self.backlogs.setdefault(origin, deque([]))
        backlog.appendleft((origin, message))

        while len(backlog) > self.bot.config["core"].get("max_backlog", 10):
            backlog.pop()

        self.bot.run_hooks("private_message", self, origin, message)

    on_invite = make_hook("invite")
    on_join = make_hook("join")
    on_kill = make_hook("kill")
    on_kick = make_hook("kick")
    on_mode_change = make_hook("mode_change")
    on_user_mode_change = make_hook("user_mode_change")
    on_nick_change = make_hook("nick_change")
    on_channel_notice = make_hook("channel_notice")
    on_private_notice = make_hook("private_notice")
    on_part = make_hook("part")
    on_topic_change = make_hook("topic_change")
    on_quit = make_hook("quit")

    on_ctcp = make_hook("ctcp")
    on_ctcp_action = make_hook("ctcp_action")
    on_ctcp_reply = make_hook("ctcp_reply")
