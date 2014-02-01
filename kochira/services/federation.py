import functools
import threading
import zmq
from zmq.eventloop import ioloop, zmqstream

from ..auth import requires_permission
from ..service import Service

service = Service(__name__)


class RequesterConnection:
    """
    A remote connection which facilitates unidirectional communication to
    request responses from an upstream federated bot via its dealer.
    """
    def __init__(self, bot, identity, url):
        self.bot = bot
        self.identity = identity
        self.url = url

        self._connect()

    def _connect(self):
        config = service.config_for(self.bot)
        storage = service.storage_for(self.bot)

        @storage.ioloop_thread.io_loop.add_callback
        def _callback():
            socket = storage.zctx.socket(zmq.DEALER)
            socket.setsockopt(zmq.IDENTITY, config["identity"].encode("utf-8"))
            socket.connect(self.url)

            self.stream = zmqstream.ZMQStream(socket,
                                              io_loop=storage.ioloop_thread.io_loop)
            self.stream.on_recv(self.on_raw_recv)

    def request(self, network, target, origin, message):
        storage = service.storage_for(self.bot)

        msg = [network.encode("utf-8"),
               target.encode("utf-8"),
               origin.encode("utf-8"),
               message.encode("utf-8")]

        service.logger.info("Sent request to %s: %s", self.identity, msg)

        @storage.ioloop_thread.io_loop.add_callback
        def _callback():
            self.stream.send_multipart(msg)

    def on_raw_recv(self, msg):
        service.logger.info("Received response from %s: %s", self.identity,
                            msg)

        network, target, origin, message = msg

        network = network.decode("utf-8")
        origin = origin.decode("utf-8")
        target = target.decode("utf-8")
        message = message.decode("utf-8")

        self.bot.networks[network].message(target,
                                           "(via {identity}): {message}".format(
            identity=self.identity,
            message=message
        ))

    def shutdown(self):
        storage = service.storage_for(self.bot)

        event = threading.Event()

        @storage.ioloop_thread.io_loop.add_callback
        def _callback():
            self.stream.close()
            event.set()

        event.wait()


class ResponderClient:
    """
    The remoting proxy takes remote queries, runs them and sends them back to
    the remote via the router.
    """
    def __init__(self, bot, identity, network):
        self.bot = bot
        self.identity = identity
        self.network = network

    @property
    def nickname(self):
        return self.identity

    def message(self, target, message):
        msg = [self.network.encode("utf-8"),
               target.encode("utf-8"),
               self.identity.encode("utf-8"),
               message.encode("utf-8")]

        service.logger.info("Sent response to %s: %s", self.identity, msg)

        storage = service.storage_for(self.bot)
        stream = storage.stream

        @storage.ioloop_thread.io_loop.add_callback
        def _callback():
            stream.send_multipart([self.identity.encode("utf-8")] + msg)


class IOLoopThread(threading.Thread):
    daemon = True

    def __init__(self):
        self.event = threading.Event()
        super().__init__()

    def run(self):
        self.io_loop = ioloop.IOLoop.instance()
        self.event.set()
        self.io_loop.start()

    def stop(self):
        self.io_loop.stop()


def on_router_recv(bot, msg):
    ident, *msg = msg

    service.logger.info("Received request from %s: %s", ident, msg)

    network, target, origin, message = msg

    ident = ident.decode("utf-8")
    network = network.decode("utf-8")
    target = target.decode("utf-8")
    origin = origin.decode("utf-8")
    message = message.decode("utf-8")

    client = ResponderClient(bot, ident, network)

    bot.run_hooks("message", client, target, origin, message)


@service.setup
def setup_federation(bot):
    config = service.config_for(bot)
    storage = service.storage_for(bot)

    storage.remotes = {}
    storage.ioloop_thread = IOLoopThread()
    storage.ioloop_thread.start()

    zctx = storage.zctx = zmq.Context()
    storage.ioloop_thread.event.wait()

    event = threading.Event()

    @storage.ioloop_thread.io_loop.add_callback
    def _callback():
        socket = zctx.socket(zmq.ROUTER)
        socket.setsockopt(zmq.IDENTITY, config["identity"].encode("utf-8"))
        socket.bind(config["bind_address"])

        storage.stream = zmqstream.ZMQStream(
            socket,
            io_loop=storage.ioloop_thread.io_loop
        )
        storage.stream.on_recv(functools.partial(on_router_recv, bot))

        for name, federation in config["federations"].items():
            if federation.get("autoconnect", False):
                storage.remotes[name] = RequesterConnection(bot, name, federation["address"])

        event.set()

    event.wait()


@service.shutdown
def shutdown_federation(bot):
    storage = service.storage_for(bot)

    event = threading.Event()

    @storage.ioloop_thread.io_loop.add_callback
    def _callback():
        for remote in storage.remotes.values():
            remote.stream.close()
        storage.stream.close()
        storage.ioloop_thread.stop()
        event.set()

    event.wait()


@service.command(r"federate with (?P<name>\S+)$", mention=True)
@requires_permission("federation")
def add_federation(client, target, origin, name):
    config = service.config_for(client.bot)
    storage = service.storage_for(client.bot)

    if name in storage.remotes:
        client.message(target, "{origin}: I'm already federating with \"{name}\".".format(
            origin=origin,
            name=name
        ))
    elif name not in config["federations"]:
        client.message(target, "{origin}: Federation with \"{name}\" is not configured.".format(
            origin=origin,
            name=name
        ))
    else:
        try:
            storage.remotes[name] = RequesterConnection(client.bot, name, config["federations"][name]["url"])
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
        remote = storage.remotes[name]
    except KeyError:
        client.message(target, "{origin}: I'm not federating with \"{name}\".".format(
            origin=origin,
            name=name
        ))
    else:
        remote.shutdown()
        del storage.remotes[name]

        client.message(target, "{origin}: Okay, I'll stop federating with \"{name}\".".format(
            origin=origin,
            name=name
        ))

@service.command(r"ask (?P<name>\S+) (?P<what>.+)$", mention=True)
def federated_request(client, target, origin, name, what):
    storage = service.storage_for(client.bot)

    try:
        remote = storage.remotes[name]
    except KeyError:
        client.message(target, "{origin}: I'm not federating with \"{name}\".".format(
            origin=origin,
            name=name
        ))
    else:
        remote.request(client.network, target, origin, what)
