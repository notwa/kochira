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

    on_join = make_hook("join")
