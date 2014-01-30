import functools
import re
import logging


class Service:
    """
    A service provides the bot with additional facilities.
    """
    SERVICES_PACKAGE = 'kochira.services'

    def __init__(self, name, commands=None, tasks=None):
        self.name = name
        self.commands = []
        self.tasks = []
        self.on_setup = []
        self.logger = logging.getLogger(self.name)

    def register_command(self, pattern, mention=False, background=False):
        """
        Register a command for use with the bot.

        ``mention`` specifies that the bot's nickname must be mentioned.
        """

        pat = re.compile(pattern)

        def _decorator(f):
            @functools.wraps(f)
            def _command_handler(client, origin, target, msg):
                if mention:
                    first, _, rest = msg.partition(" ")
                    first = first.rstrip(",:")

                    if first != client.nickname:
                        return

                    msg = rest

                match = pat.match(msg)
                if match is None:
                    return

                kwargs = match.groupdict()

                for k, v in kwargs.items():
                    if k in f.__annotations__ and v is not None:
                        kwargs[k] = f.__annotations__[k](v)

                if background:
                    client.bot.executor.submit(f, client, origin, target, **kwargs)
                else:
                    f(client, origin, target, **kwargs)

            self.commands.append(_command_handler)
            return f

        return _decorator


    def register_task(self, interval):
        """
        Register a new periodic task. For one-off tasks that need to be
        deferred to a thread, use ``bot.executor.submit``.
        """

        def _decorator(f):
            self.tasks.append((f, interval))
            return f

        return _decorator

    def register_setup(self, f):
        """
        Register a setup function.
        """
        self.on_setup.append(f)

    def dispatch_commands(self, client, origin, target, message):
        """
        Attempt to dispatch a command to all command handlers.
        """

        for command in self.commands:
            try:
                command(client, origin, target, message)
            except BaseException:
                self.logger.error("Command processing failed", exc_info=True)

    def setup(self, bot, storage):
        """
        Run all setup functions for the service.
        """
        for setup in self.on_setup:
            setup(bot, storage)

    def tasks_for_time_slice(self):
        """
        Get the tasks that should run for this time slice.
        """

    def config_for(self, bot):
        """
        Get the configuration dictionary.
        """
        return bot.config["services"][self.name]

    def storage_for(self, bot):
        """
        Get the disposable storage object.
        """
        _, storage = bot.services[self.name]
        return storage
