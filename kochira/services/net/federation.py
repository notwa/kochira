"""
Bot request federation.

This service allows bots to run requests on other bots via a federation
protocol.

Protocol
========

The protocol is implemented over ZeroMQ.

Terminology
-----------

requester
  A ZeroMQ DEALER socket that connects to another bot's responder socket. One
  requester socket used per bot.

responder
  A ZeroMQ ROUTER socket that accepts connections from other bot's responder
  sockets. This socket can accept any number of connections.

Message Format
--------------

All messages on the protocol are sent in multi-part. Where "remaining IRC
payload..." is used, it indicates the parsed result of an IRC command, starting
with the command name (e.g. ``["PRIVMSG", "#foo", "test"]``).

me
  Refers to the local bot.

you
  Refers to a remote bot.

this requester, other responder
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

I (this requester) need to make a request to you (other responder)::

    [
        my network name,
        my requesting user's hostmask,
        remaining IRC payload (request)...
    ]

this responder, other requester
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You (other requester) need a response from me (this responder)::

    [
        your identity,
        my network name,
        my bot's hostmask,
        remaining IRC payload (response)...
    ]
"""

import functools
import zmq
import zmq.auth
from zmq.eventloop import zmqstream

from kochira import config
from kochira.auth import requires_permission
from kochira.service import Service

service = Service(__name__, __doc__)


@service.config
class Config(config.Config):
    class Federation(config.Config):
        autoconnect = config.Field(doc="Whether the bot should attempt to " \
                                       "autoconnect to the federation.")
        url = config.Field(doc="The remote URL to connect to.")
        username = config.Field(doc="The username to use when connecting.")
        password = config.Field(doc="The password to use when connecting.")

    identity = config.Field(doc="Unique name across all federations.")
    bind_address = config.Field(doc="Address to bind to, e.g. ``tcp://*:9999``.")
    users = config.Field(doc="A key-value mapping of users to their passwords.",
                         type=config.Mapping(str))
    federations = config.Field(doc="A key-value mapping of bots this " \
                                   "instance is able to federate to. The key " \
                                   "refers to the bot's unique identity " \
                                   "specified in the configuration.",
                               type=config.Mapping(Federation))


class RequesterConnection:
    """
    A remote connection which facilitates unidirectional communication to
    request responses from an upstream federated bot via its dealer.
    """
    def __init__(self, bot, identity, config):
        self.bot = bot
        self.identity = identity
        self.config = config

        self._connect()

    def _connect(self):
        config = service.config_for(self.bot)
        storage = service.storage_for(self.bot)

        @self.bot.io_loop.add_callback
        def _callback():
            socket = storage.zctx.socket(zmq.DEALER)
            socket.identity = config.identity.encode("utf-8")

            if "username" in self.config:
                socket.plain_username = self.config.username.encode("utf-8")

            if "password" in self.config:
                socket.plain_password = self.config.password.encode("utf-8")

            socket.connect(self.config.url)

            self.stream = zmqstream.ZMQStream(socket,
                                              io_loop=self.bot.io_loop)
            self.stream.on_recv(self.on_raw_recv)

    def request(self, network, target, origin, message):
        msg = [network.encode("utf-8"),
               (origin + "!user@federated/kochira/" + origin).encode("utf-8"),
               b"PRIVMSG",
               target.encode("utf-8"),
               message.encode("utf-8")]

        @self.bot.io_loop.add_callback
        def _callback():
            service.logger.info("Sent request to %s: %s", self.identity, msg)
            self.stream.send_multipart(msg)

    def on_raw_recv(self, msg):
        service.logger.info("Received response from %s: %s", self.identity,
                            msg)

        network, origin, type, *args = msg

        network = network.decode("utf-8")
        origin, _, _ = origin.decode("utf-8").partition("!")

        if type == b"PRIVMSG":
            target, message = args

            target = target.decode("utf-8")
            message = message.decode("utf-8")

            self.bot.networks[network].message(
                target,
                "(via {identity}) {message}".format(
                    identity=self.identity,
                    message=message
                )
            )

    def shutdown(self):
        @self.bot.io_loop.add_callback
        def _callback():
            self.stream.close()


class ResponderClient:
    """
    The remoting proxy takes remote queries, runs them and sends them back to
    the remote via the router.
    """
    def __init__(self, bot, remote_name, network, target):
        self.bot = bot
        self.remote_name = remote_name
        self.network = network
        self.target = target

    @property
    def nickname(self):
        return service.config_for(self.bot)["identity"]

    def __getattr__(self, key):
        self.unsupported()

    def unsupported(self):
        self.message(self.target, "Operation not supported in federated mode.")
        raise RuntimeError("operation not supported in federated mode")

    def message(self, target, message):
        msg = [self.network.encode("utf-8"),
               (self.nickname + "!bot@federated/kochira/" + self.nickname).encode("utf-8"),
               b"PRIVMSG",
               target.encode("utf-8"),
               message.encode("utf-8")]

        storage = service.storage_for(self.bot)
        stream = storage.stream

        @self.bot.io_loop.add_callback
        def _callback():
            service.logger.info("Sent response to %s: %s", self.remote_name,
                                msg)
            stream.send_multipart([self.remote_name.encode("utf-8")] + msg)


def on_router_recv(bot, msg):
    ident, *msg = msg

    service.logger.info("Received request from %s: %s", ident, msg)

    network, origin, type, *args = msg

    ident = ident.decode("utf-8")
    network = network.decode("utf-8")
    origin, _, _ = origin.decode("utf-8").partition("!")

    if type == b"PRIVMSG":
        target, message = args

        target = target.decode("utf-8")
        message = message.decode("utf-8")

        client = ResponderClient(bot, ident, network, target)

        bot.run_hooks("channel_message", client, target, origin, message)


@service.setup
def setup_federation(bot):
    config = service.config_for(bot)
    storage = service.storage_for(bot)

    storage.federations = {}

    zctx = storage.zctx = zmq.Context()

    @bot.io_loop.add_callback
    def _callback():
        auth = storage.auth = zmq.auth.IOLoopAuthenticator(zctx,
                                                           io_loop=bot.io_loop)
        auth.start()
        auth.configure_plain(domain="*",
                             passwords=config.users)

        socket = zctx.socket(zmq.ROUTER)
        socket.identity = config.identity.encode("utf-8")
        socket.plain_server = True
        socket.bind(config.bind_address)

        storage.stream = zmqstream.ZMQStream(socket, io_loop=bot.io_loop)
        storage.stream.on_recv(functools.partial(on_router_recv, bot))

        for name, federation in config.federations.items():
            if federation.get("autoconnect", False):
                storage.federations[name] = RequesterConnection(bot, name,
                                                                federation)


@service.shutdown
def shutdown_federation(bot):
    storage = service.storage_for(bot)

    @bot.io_loop.add_callback
    def _callback():
        try:
            storage.auth.stop()
        except Exception as e:
            service.logger.error("Error during federation shut down",
                                 exc_info=e)

        for remote in storage.federations.values():
            try:
                remote.stream.close()
            except Exception as e:
                service.logger.error("Error during federation shut down",
                                     exc_info=e)

        try:
            storage.stream.close()
        except Exception as e:
            service.logger.error("Error during federation shut down",
                                 exc_info=e)


@service.command(r"federate with (?P<name>\S+)$", mention=True)
@requires_permission("federation")
def add_federation(client, target, origin, name):
    """
    Federate.

    ::

        $bot: federate with <name>

    Connect to a bot specified in the federation configuration.
    """

    config = service.config_for(client.bot)
    storage = service.storage_for(client.bot)

    if name in storage.federations:
        client.message(target, "{origin}: I'm already federating with \"{name}\".".format(
            origin=origin,
            name=name
        ))
    elif name not in config.federations:
        client.message(target, "{origin}: Federation with \"{name}\" is not configured.".format(
            origin=origin,
            name=name
        ))
    else:
        try:
            storage.federations[name] = RequesterConnection(client.bot, name, config.federations[name])
        except Exception as e:
            client.message(target, "{origin}: Sorry, I couldn't federate with \"{name}\".".format(
                origin=origin,
                name=name
            ))
            client.message(target, "↳ {name}: {info}".format(
                name=e.__class__.__name__,
                info=str(e)
            ))
        else:
            client.message(target, "{origin}: Okay, I'll federate with \"{name}\".".format(
                origin=origin,
                name=name
            ))


@service.command(r"stop federating with (?P<name>\S+)$", mention=True)
@service.command(r"don't federate with (?P<name>\S+)$", mention=True)
@requires_permission("federation")
def remove_federation(client, target, origin, name):
    """
    Unfederate.

    ::

        $bot: stop federating with <name>
        $bot: don't federate with <name>

    Disconnect from a bot.
    """

    storage = service.storage_for(client.bot)

    try:
        remote = storage.federations[name]
    except KeyError:
        client.message(target, "{origin}: I'm not federating with \"{name}\".".format(
            origin=origin,
            name=name
        ))
    else:
        remote.shutdown()
        del storage.federations[name]

        client.message(target, "{origin}: Okay, I'll stop federating with \"{name}\".".format(
            origin=origin,
            name=name
        ))

@service.command(r"ask (?P<name>\S+) (?P<what>.+)$", mention=True)
@service.command(r"\*(?P<name>\S+)(?P<mode>:|>) (?P<what>.+)$")
def federated_request(client, target, origin, name, what, mode=None):
    """
    Federated request.

    ::

        $bot: ask <name> <what>
        *<name>> <what>
        *<name>: <what>

    The first two forms of the command directly send a request to the federated
    bot. The third form will append the bot's name, mentioning it, before sending
    it to the federated bot.
    """

    storage = service.storage_for(client.bot)

    try:
        remote = storage.federations[name]
    except KeyError:
        client.message(target, "{origin}: I'm not federating with \"{name}\".".format(
            origin=origin,
            name=name
        ))
    else:
        if mode == ":":
            what = name + ": " + what
        remote.request(client.network, target, origin, what)


@service.command(r"who are you federated with\??$", mention=True)
@service.command(r"(?:list (?:all )?)?federations$", mention=True)
def list_federations(client, target, origin):
    """
    List federations.

    ::

        $bot: who are you federated with
        $bot: federations
        $bot: list federations
        $bot: list all federations

    List all bots this bot is federating with.
    """

    storage = service.storage_for(client.bot)

    client.message(target, "I am federated with: {federation}".format(
        federation=", ".join(storage.federations))
    )

