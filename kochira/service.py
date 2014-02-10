import functools
import re
import logging
import bisect

from . import config

logger = logging.getLogger(__name__)


class Config(config.Config):
    autoload = config.Field(doc="Autoload this service?", default=False)
    enabled = config.Field(doc="Enable this service?", default=True)


class Service:
    """
    A service provides the bot with additional facilities.
    """
    SERVICES_PACKAGE = 'kochira.services'

    EAT = object()

    def __init__(self, name, doc=None):
        self.name = name
        self.doc = doc
        self.hooks = {}
        self.commands = set([])
        self.tasks = []
        self.config_factory = Config
        self.on_setup = None
        self.on_shutdown = None
        self.logger = logging.getLogger(self.name)

    def hook(self, hook, priority=0):
        """
        Register a hook with the service.
        """

        def _decorator(f):
            bisect.insort(self.hooks.setdefault(hook, []), (-priority, id(f), f))
            f.service = self
            return f

        return _decorator

    def command(self, pattern, priority=0, mention=False, strip=True,
                re_flags=re.I, eat=True, allow_private=True):
        """
        Register a command for use with the bot.

        ``mention`` specifies that the bot's nickname must be mentioned.
        """

        if pattern[-1] != "$":
            pattern += "$"
        pat = re.compile(pattern, re_flags)

        def _decorator(f):
            if not hasattr(f, "patterns"):
                f.patterns = set([])

            f.patterns.add((pattern, mention))

            @functools.wraps(f)
            def _command_handler(client, origin, target, message):
                if strip:
                    message = message.strip()

                # check if we're either being mentioned or being PMed
                if mention and origin != target:
                    first, _, rest = message.partition(" ")
                    first = first.rstrip(",:")

                    if first.lower() != client.nickname.lower():
                        return

                    message = rest

                match = pat.match(message)
                if match is None:
                    return

                kwargs = match.groupdict()

                for k, v in kwargs.items():
                    if k in f.__annotations__ and v is not None:
                        kwargs[k] = f.__annotations__[k](v)

                r = f(client, origin, target, **kwargs)

                if r is not None:
                    return r

                if eat:
                    return Service.EAT

            self.hook("channel_message", priority=priority)(_command_handler)

            if allow_private:
                self.hook("private_message", priority=priority)(
                    lambda client, origin, message: _command_handler(client, origin, origin, message)
                )

            self.commands.add(f)
            return f

        return _decorator

    def task(self, f):
        """
        Register a new task. If the task is designed to be used as a timer,
        interval should be `None`.
        """

        f.service = self
        self.tasks.append(f)
        return f

    def config(self, factory):
        """
        Register a configuration factory.
        """
        self.config_factory = factory
        return factory

    def setup(self, f):
        """
        Register a setup function.
        """
        self.on_setup = f
        return f

    def shutdown(self, f):
        """
        Register a shutdown function.
        """
        self.on_shutdown = f
        return f

    def run_setup(self, bot):
        """
        Run all setup functions for the service.
        """
        if self.on_setup is not None:
            self.on_setup(bot)

    def run_shutdown(self, bot):
        """
        Run all setup functions for the service.
        """
        if self.on_shutdown is not None:
            self.on_shutdown(bot)

    def config_for(self, bot, network=None, channel=None):
        """
        Get the configuration settings.
        """
        config = bot.config.services.get(self.name, self.config_factory())

        if network is not None:
            network_config = bot.config.networks[network]
            config = config.combine(network_config.services.get(self.name, self.config_factory()))

            if channel is not None:
                if channel in network_config.channels:
                    channel_config = network_config.channels[channel]
                    config = config.combine(channel_config.services.get(self.name, self.config_factory()))

        return config

    def storage_for(self, bot):
        """
        Get the disposable storage object.
        """
        _, storage = bot.services[self.name]
        return storage


def background(f):
    """
    Defer a command to run in the background.
    """

    f.background = True

    @functools.wraps(f)
    def _inner(client, *args, **kwargs):
        future = client.bot.executor.submit(f, client, *args, **kwargs)

        @future.add_done_callback
        def on_complete(future):
            exc = future.exception()
            if exc is not None:
                logger.error("Command error", exc_info=exc)

    return _inner
