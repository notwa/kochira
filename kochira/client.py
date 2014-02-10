import logging
from collections import deque
import textwrap

from pydle import Client as _Client
from pydle.features.rfc1459.protocol import MESSAGE_LENGTH_LIMIT

from .service import Service

logger = logging.getLogger(__name__)


class Client(_Client):
    def __init__(self, bot, network, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.backlogs = {}
        self.bot = bot

        # set network name to whatever we have in our config
        self.network = network

    def _send_message(self, message):
        self.bot.defer_from_thread(super()._send_message, message)

    def on_ctcp_version(self, by, target, message):
        self.ctcp_reply(by, "VERSION",
                        self.bot.config.core.version)

    def on_connect(self):
        logger.info("Connected to IRC network: %s", self.network)
        super().on_connect()

    def _autotruncate(self, command, target, message, suffix="..."):
        hostmask = self._format_hostmask(self.nickname)
        chunklen = MESSAGE_LENGTH_LIMIT - len('{hostmask} {command} {target} :'.format(
            hostmask=hostmask,
            command=command,
            target=target
        )) - 25

        if len(message) > chunklen:
            message = textwrap.wrap(message, chunklen - len(suffix))[0] + suffix

        return message

    def message(self, target, message):
        message = self._autotruncate("PRIVMSG", target, message)

        super().message(target, message)
        self.bot.defer_from_thread(self.bot.run_hooks,
                                   "own_message", self, target, message)

    def notice(self, target, message):
        message = self._autotruncate("PRIVMSG", target, message)

        super().notice(target, message)
        self.bot.defer_from_thread(self.bot.run_hooks,
                                   "own_notice", self, target, message)

    def on_channel_message(self, target, origin, message):
        backlog = self.backlogs.setdefault(target, deque([]))
        backlog.appendleft((origin, message))

        while len(backlog) > self.bot.config.core.max_backlog:
            backlog.pop()

    def on_private_message(self, origin, message):
        backlog = self.backlogs.setdefault(origin, deque([]))
        backlog.appendleft((origin, message))

        while len(backlog) > self.bot.config.core.max_backlog:
            backlog.pop()

    def _run_hooks(self, name, *args, **kwargs):
        for hook in self.bot.get_hooks(name):
            config = hook.service.config_for(self.bot, self.network)

            if not config.enabled:
                continue

            try:
                r = hook(self, *args, **kwargs)
                if r is Service.EAT:
                    return Service.EAT
            except BaseException:
                logger.error("Hook processing failed", exc_info=True)


    def __getattribute__(self, name):
        if name.startswith("on_"):
            # automatically generate a hook runner for all on_ functions
            hook_name = name[3:]

            try:
                f = _Client.__getattribute__(self, name)
            except AttributeError:
                def _magic_hook(*args, **kwargs):
                    self._run_hooks(hook_name, *args, **kwargs)
            else:
                def _magic_hook(*args, **kwargs):
                    r = f(*args, **kwargs)
                    self._run_hooks(hook_name, *args, **kwargs)
                    return r

            return _magic_hook
        else:
            return _Client.__getattribute__(self, name)
