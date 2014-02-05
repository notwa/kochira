from concurrent.futures import ThreadPoolExecutor
import imp
import importlib
import heapq
import logging
import multiprocessing
from peewee import SqliteDatabase
import yaml
from zmq.eventloop import ioloop

from .auth import ACLEntry
from .client import Client
from .db import database
from .scheduler import Scheduler
from .util import Expando
from .service import Service

logger = logging.getLogger(__name__)


class Bot:
    """
    The core bot.
    """

    def __init__(self, config_file="config.yml"):
        self.services = {}
        self.networks = {}
        self.io_loop = ioloop.IOLoop()

        self.config_file = config_file

        self.rehash()
        self._connect_to_db()

    def run(self):
        self.executor = ThreadPoolExecutor(multiprocessing.cpu_count())
        self.scheduler = Scheduler(self)
        self.scheduler.start()

        self._load_services()
        self._connect_to_irc()

    def connect(self, network_name):
        config = self.config["networks"][network_name]

        client = Client(self, network_name, config["nickname"])
        client.connect(hostname=config["hostname"], port=config.get("port"),
                       password=config.get("password"),
                       tls=config.get("tls", False),
                       tls_verify=config.get("tls_verify", True))

        if "sasl" in config:
            client.sasl_username = config["sasl"]["username"]
            client.sasl_password = config["sasl"]["password"]

        self.networks[network_name] = client
        self.io_loop.add_handler(client.connection.socket.fileno(),
                                 lambda fd, events: client._handle_message(),
                                 ioloop.IOLoop.READ)

        return client

    def disconnect(self, network_name):
        client = self.networks[network_name]
        fileno = client.connection.socket.fileno()
        self.io_loop.remove_handler(fileno)

        try:
            client.quit()
        finally:
            del self.networks[network_name]

    def _connect_to_db(self):
        database.initialize(SqliteDatabase(self.config["core"].get("database", "kochira.db"),
                                           threadlocals=True))
        logger.info("Opened database connection: %s", self.config["core"]["database"])

        ACLEntry.create_table(True)

    def _connect_to_irc(self):
        for network_name, config in self.config["networks"].items():
            if config.get("autoconnect", False):
                self.connect(network_name)

        self.io_loop.start()

    def _load_services(self):
        for service, config in self.config["services"].items():
            if config.get("autoload"):
                try:
                    self.load_service(service)
                except:
                    pass # it gets logged

    def _shutdown_service(self, service):
        service.run_shutdown(self)
        self.scheduler.unschedule_service(service)

    def load_service(self, name, reload=False):
        """
        Load a service into the bot.

        The service should expose a variable named ``service`` which is an
        instance of ``kochira.service.Service`` and configured appropriately.
        """

        # ensure that the service's shutdown routine is run
        if name in self.services:
            service, _ = self.services[name]
            self._shutdown_service(service)

        # we create an expando storage first for bots to load any locals they
        # need
        service = None
        storage = Expando()

        try:
            module = importlib.import_module(name)

            if reload:
                module = imp.reload(module)

            if not hasattr(module, "service"):
                raise RuntimeError("{} is not a valid service".format(name))

            service = module.service
            self.services[service.name] = (service, storage)

            service.run_setup(self)
        except:
            logger.error("Couldn't load service %s", name, exc_info=True)
            if service is not None:
                del self.services[service.name]
            raise

        logger.info("Loaded service %s", name)

    def unload_service(self, name):
        """
        Unload a service from the bot.
        """
        service, _ = self.services[name]
        self._shutdown_service(service)
        del self.services[name]

    def _compute_hooks(self, hook):
        """
        Create an ordering of hooks to run.
        """

        return (hook for _, _, hook in heapq.merge(*[
            service.hooks.get(hook, [])
            for service, storage in list(self.services.values())
        ]))

    def run_hooks(self, hook, client, *args):
        """
        Attempt to dispatch a command to all command handlers.
        """

        for hook in self._compute_hooks(hook):
            try:
                r = hook(client, *args)
                if r is Service.EAT:
                    return Service.EAT
            except BaseException:
                logger.error("Hook processing failed", exc_info=True)

    def rehash(self):
        """
        Reload configuration information.
        """

        with open(self.config_file, "r") as f:
            self.config = yaml.load(f)


def main():
    import sys

    logging.basicConfig(level=logging.INFO)
    bot = Bot(sys.argv[1] if len(sys.argv) > 1 else "config.yml")
    bot.run()
