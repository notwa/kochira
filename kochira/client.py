import logging
from collections import deque
from datetime import timedelta
import textwrap

from pydle import Client as _Client
from pydle.features.rfc1459.protocol import MESSAGE_LENGTH_LIMIT

from zmq.eventloop import ioloop

from .service import Service

logger = logging.getLogger(__name__)


class Client(_Client):
    RECONNECT_BACKOFF = [0, 5, 10, 20, 40, 80, 120]

    def __init__(self, bot, name, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._reconnect_timeout = None
        self._fd = None

        self.backlogs = {}
        self.bot = bot

        self.name = name

    @classmethod
    def from_config(cls, bot, network_name, config):
        client = cls(bot, network_name, config.nickname,
            username=config.username,
            realname=config.realname,
            tls_client_cert=config.tls.certificate_file,
            tls_client_cert_key=config.tls.certificate_keyfile,
            tls_client_cert_password=config.tls.certificate_password,
            sasl_username=config.sasl.username,
            sasl_password=config.sasl.password
        )

        client.connect(
            hostname=config.hostname,
            password=config.password,
            source_address=(config.source_address, 0),
            port=config.port,
            tls=config.tls.enabled,
            tls_verify=config.tls.verify
        )

        return client

    def _handle_next_message(self, fd, events):
        if self.connection.socket is None or not self.connection.receive_data():
            # connection was closed
            logging.warn("Lost connection: %s", self.name)
            self.on_disconnect(False)
            return

        if self.connection.parse_data():
            while len(self.connection.message_queue) > 0:
                self.on_raw(self.connection.get_message())

    def connect(self, *args, reconnect=False, attempt=0, **kwargs):
        logger.info("Connecting: %s", self.name)

        try:
            super().connect(*args, reconnect=reconnect, **kwargs)
        except (OSError, IOError) as e:
            backoff = Client.RECONNECT_BACKOFF[min(
                attempt,
                len(Client.RECONNECT_BACKOFF) - 1
            )]

            logger.warning("Couldn't connect: %s, reattempting in %d seconds: %s",
                            self.name, backoff, e)

            self._reconnect_timeout = self.bot.io_loop.add_timeout(
                timedelta(seconds=backoff),
                lambda: self.connect(*args, reconnect=reconnect,
                                     attempt=attempt + 1, **kwargs)
            )
        else:
            self.fd = self.connection.socket.fileno()
            self.bot.io_loop.add_handler(self.fd, self._handle_next_message,
                                         ioloop.IOLoop.READ)

    def on_disconnect(self, expected):
        self._reset_attributes()

        if self._reconnect_timeout is not None:
            self.bot.io_loop.remove_timeout(self._reconnect_timeout)
            self._reconnect_timeout = None

        self.bot.io_loop.remove_handler(self.fd)
        self.fd = None

        self._run_hooks("disconnect", None, [expected])

        if not expected:
            self.connect(reconnect=True)

    def _send_message(self, message):
        self.bot.defer_from_thread(super()._send_message, message)

    def on_ctcp_version(self, by, what, contents):
        self.ctcp_reply(by, "VERSION", self.bot.config.core.version)

    def on_connect(self):
        logger.info("Connected to IRC network: %s", self.name)
        super().on_connect()

        for name, channel in self.bot.config.networks[self.name].channels.items():
            self.join(name, password=channel.password)

        self._run_hooks("connect", None)

    def _autotruncate(self, command, target, message, suffix="..."):
        hostmask = self._format_hostmask(self.nickname)
        chunklen = MESSAGE_LENGTH_LIMIT - len("{hostmask} {command} {target} :".format(
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
        self.bot.defer_from_thread(self._run_hooks, "own_message", target,
                                   [target, message])

    def notice(self, target, message):
        message = self._autotruncate("PRIVMSG", target, message)

        super().notice(target, message)
        self.bot.defer_from_thread(self._run_hooks, "own_notice", target,
                                   [target, message])

    def _run_hooks(self, name, target, args=None, kwargs=None):
        if args is None:
            args = []

        if kwargs is None:
            kwargs = {}

        for hook in self.bot.get_hooks(name):
            config = hook.service.config_for(self.bot, self.name, target)

            if not config.enabled:
                continue

            try:
                r = hook(self, *args, **kwargs)
                if r is Service.EAT:
                    return Service.EAT
            except BaseException:
                logger.error("Hook processing failed", exc_info=True)

    def on_invite(self, channel, by):
        self._run_hooks("invite", by, [channel, by])

    def on_join(self, channel, user):
        self._run_hooks("join", channel, [channel, user])

    def on_kill(self, target, by, reason):
        self._run_hooks("kill", by, [target, by, reason])

    def on_kick(self, channel, target, by, reason=None):
        self._run_hooks("kick", channel, [channel, target, by, reason])

    def on_mode_change(self, channel, modes, by):
        self._run_hooks("mode_change", channel, [channel, modes, by])

    def on_user_mode_change(self, modes):
        self._run_hooks("user_mode_change", None, [modes])

    def on_channel_message(self, target, by, message):
        backlog = self.backlogs.setdefault(target, deque([]))
        backlog.appendleft((by, message))

        while len(backlog) > self.bot.config.core.max_backlog:
            backlog.pop()

        self._run_hooks("channel_message", target, [target, by, message])

    def on_private_message(self, by, message):
        backlog = self.backlogs.setdefault(by, deque([]))
        backlog.appendleft((by, message))

        while len(backlog) > self.bot.config.core.max_backlog:
            backlog.pop()

        self._run_hooks("private_message", by, [by, message])

    def on_nick_change(self, old, new):
        self._run_hooks("nick_change", new, [old, new])

    def on_channel_notice(self, target, by, message):
        self._run_hooks("channel_notice", target, [target, by, message])

    def on_private_notice(self, by, message):
        self._run_hooks("private_notice", by, [by, message])

    def on_part(self, channel, user, message=None):
        self._run_hooks("part", channel, [channel, user, message])

    def on_topic_change(self, channel, message, by):
        self._run_hooks("topic_change", channel, [channel, message, by])

    def on_quit(self, user, message=None):
        self._run_hooks("quit", user, [user, message])

    def on_ctcp(self, by, what, contents):
        self._run_hooks("ctcp", by, [by, what, contents])

    def on_ctcp_action(self, by, what, contents):
        self._run_hooks("ctcp_action", by, [by, what, contents])
