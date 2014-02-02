import functools
import threading
import zmq
import zmq.auth
from zmq.eventloop import ioloop, zmqstream

from ..auth import requires_permission
from ..service import Service

service = Service(__name__)


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

        @storage.ioloop_thread.io_loop.add_callback
        def _callback():
            socket = storage.zctx.socket(zmq.DEALER)
            socket.identity = config["identity"].encode("utf-8")

            if "username" in self.config:
                socket.plain_username = self.config["username"].encode("utf-8")

            if "password" in self.config:
                socket.plain_password = self.config["password"].encode("utf-8")

            socket.connect(self.config["url"])

            self.stream = zmqstream.ZMQStream(socket,
                                              io_loop=storage.ioloop_thread.io_loop)
            self.stream.on_recv(self.on_raw_recv)

    def request(self, network, target, origin, message):
        storage = service.storage_for(self.bot)

        msg = [network.encode("utf-8"),
               (origin + "!user@federated/kochira/" + origin).encode("utf-8"),
               b"PRIVMSG",
               target.encode("utf-8"),
               message.encode("utf-8")]

        @storage.ioloop_thread.io_loop.add_callback
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

            self.bot.networks[network].message(target,
                                               "(via {identity}) {message}".format(
                identity=self.identity,
                message=message
            ))

    def shutdown(self):
        storage = service.storage_for(self.bot)

        event = threading.Event()

        @storage.ioloop_thread.io_loop.add_callback
        def _callback():
            try:
                self.stream.close()
            finally:
                event.set()

        event.wait()


class UnsupportedUserCollection:
    def __init__(self, client):
        self.client = client

    def __contains__(self, key):
        self.client.unsupported()

    def __getitem__(self, key):
        self.client.unsupported()


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
        self.users = UnsupportedUserCollection(self)

    @property
    def nickname(self):
        return service.config_for(self.bot)["identity"]

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

        @storage.ioloop_thread.io_loop.add_callback
        def _callback():
            service.logger.info("Sent response to %s: %s", self.remote_name,
                                msg)
            stream.send_multipart([self.remote_name.encode("utf-8")] + msg)


class IOLoopThread(threading.Thread):
    daemon = True

    def __init__(self):
        self.event = threading.Event()
        super().__init__()

    def run(self):
        try:
            self.io_loop = ioloop.IOLoop()
        finally:
            self.event.set()

        self.io_loop.start()

    def stop(self):
        @self.io_loop.add_callback
        def _callback():
            self.io_loop.stop()


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

        bot.run_hooks("message", client, target, origin, message)


@service.setup
def setup_federation(bot):
    config = service.config_for(bot)
    storage = service.storage_for(bot)

    storage.federations = {}
    storage.ioloop_thread = IOLoopThread()
    storage.ioloop_thread.start()

    zctx = storage.zctx = zmq.Context()

    storage.ioloop_thread.event.wait()

    event = threading.Event()

    @storage.ioloop_thread.io_loop.add_callback
    def _callback():
        try:
            auth = storage.auth = zmq.auth.IOLoopAuthenticator(
                zctx,
                io_loop=storage.ioloop_thread.io_loop
            )
            auth.start()
            auth.configure_plain(domain="*",
                                 passwords=config.get("users", {}))

            socket = zctx.socket(zmq.ROUTER)
            socket.identity = config["identity"].encode("utf-8")
            socket.plain_server = True
            socket.bind(config["bind_address"])

            storage.stream = zmqstream.ZMQStream(
                socket,
                io_loop=storage.ioloop_thread.io_loop
            )
            storage.stream.on_recv(functools.partial(on_router_recv, bot))

            for name, federation in config.get("federations", {}).items():
                if federation.get("autoconnect", False):
                    storage.federations[name] = RequesterConnection(bot, name, federation)
        finally:
            event.set()

    event.wait()


@service.shutdown
def shutdown_federation(bot):
    storage = service.storage_for(bot)

    event = threading.Event()

    @storage.ioloop_thread.io_loop.add_callback
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

        event.set()

    event.wait()

    storage.ioloop_thread.stop()


@service.command(r"federate with (?P<name>\S+)$", mention=True)
@requires_permission("federation")
def add_federation(client, target, origin, name):
    config = service.config_for(client.bot)
    storage = service.storage_for(client.bot)

    if name in storage.federations:
        client.message(target, "{origin}: I'm already federating with \"{name}\".".format(
            origin=origin,
            name=name
        ))
    elif name not in config.get("federations", {}):
        client.message(target, "{origin}: Federation with \"{name}\" is not configured.".format(
            origin=origin,
            name=name
        ))
    else:
        try:
            storage.federations[name] = RequesterConnection(client.bot, name, config["federations"][name])
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
@service.command(r"~(?P<name>\S+)(?P<mode>:|>) (?P<what>.+)$")
def federated_request(client, target, origin, name, what, mode=None):
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
    storage = service.storage_for(client.bot)

    client.message(target, "I am federated with: {federation}".format(
        federation=", ".join(storage.federations))
    )

