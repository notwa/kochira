import functools
import re
import logging
import bisect

from pydle.async import coroutine, Future

from .auth import has_permission, requires_permission
from . import config

from .util import Expando

logger = logging.getLogger(__name__)


class Config(config.Config):
    autoload = config.Field(doc="Autoload this service?", default=True)
    enabled = config.Field(doc="Enable this service?", default=True)


class BoundService:
    def __init__(self, service):
        self.service = service
        self.storage = Expando()
        self.contexts = {}


class Service:
    """
    A service provides the bot with additional facilities.
    """

    EAT = object()

    def __init__(self, name, doc=None):
        self.name = name
        self.doc = doc
        self.hooks = {}
        self.commands = set([])
        self.models = set([])
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
            @coroutine
            def _command_handler(client, target, origin, message):
                contexts = getattr(f, "contexts", set([]))
                if contexts:
                    # check for contexts
                    bound = self.binding_for(client.bot)

                    my_contexts = \
                        bound.contexts.get(client.name, {}).get(target, set([])) | \
                        bound.contexts.get(client.name, {}).get(None, set([]))

                    if not my_contexts & contexts:
                        return

                # check for permissions
                permissions = getattr(f, "permissions", set([]))

                hostmask = "{nickname}!{username}@{hostname}".format(
                    nickname=origin,
                    username=client.users[origin]["username"],
                    hostname=client.users[origin]["hostname"]
                )
                if not all(has_permission(client, hostmask, permission, target) for permission in permissions):
                    return

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

                r = f(client, target, origin, **kwargs)

                if isinstance(r, Future):
                    r = yield r

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

    def _autocreate_models(self):
        for model in self.models:
            model.create_table(True)

    def run_setup(self, bot):
        """
        Run all setup functions for the service.
        """
        self._autocreate_models()
        if self.on_setup is not None:
            self.on_setup(bot)

    def run_shutdown(self, bot):
        """
        Run all shutdown functions for the service.
        """

        # unschedule remaining work
        bot.scheduler.unschedule_service(self)

        if self.on_shutdown is not None:
            self.on_shutdown(bot)

    def config_for(self, bot, client_name=None, channel=None):
        """
        Get the configuration settings.
        """
        config = bot.config.services.get(self.name, self.config_factory())

        if client_name is not None:
            client_config = bot.config.clients[client_name]
            config = config.combine(client_config.services.get(self.name, self.config_factory()))

            if channel is not None:
                if channel in client_config.channels:
                    channel_config = client_config.channels[channel]
                    config = config.combine(channel_config.services.get(self.name, self.config_factory()))

        return config

    def storage_for(self, bot):
        """
        Get the disposable storage object.
        """
        return self.binding_for(bot).storage

    def binding_for(self, bot):
        """
        Get the service binding.
        """
        return bot.services[self.name]

    def model(self, model):
        self.models.add(model)
        return model

    def add_context(self, client, context, target=None):
        self.binding_for(client.bot).contexts \
            .setdefault(client.name, {}) \
            .setdefault(target, set([])).add(context)

    def has_context(self, client, context, target=None):
        return context in self.binding_for(client.bot).contexts \
            .get(client.name, {}) \
            .get(target, set([]))

    def remove_context(self, client, context, target=None):
        self.binding_for(client.bot).contexts[client.name][target].remove(context)


def background(f):
    """
    Defer a command to run in the background.
    """

    f.background = True

    @functools.wraps(f)
    @coroutine
    def _inner(client, *args, **kwargs):
        result = yield client.bot.executor.submit(f, client, *args, **kwargs)
        if isinstance(result, Future):
            result = yield result
        return result

    return _inner


def requires_context(context):
    """
    Require a context for the command.
    """

    def _decorator(f):
        if not hasattr(f, "contexts"):
            f.contexts = set([])
        f.contexts.add(context)

        return f
    return _decorator
