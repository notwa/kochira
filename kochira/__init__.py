from concurrent.futures import ThreadPoolExecutor
import imp
import importlib
import logging
import multiprocessing
from peewee import SqliteDatabase
import yaml

from pydle.client import ClientPool

from .auth import ACLEntry
from .client import Client
from .db import database
from .scheduler import Scheduler
from .util import Expando

logger = logging.getLogger(__name__)


class Bot:
    """
    The core bot.
    """

    def __init__(self, config_file="config.yml"):
        self.services = {}
        self.config_file = config_file

        self.rehash()
        self._connect_to_db()

    def run(self):
        self.executor = ThreadPoolExecutor(multiprocessing.cpu_count())
        self.scheduler = Scheduler(self)
        self.scheduler.start()

        self._load_services()
        self._connect_to_irc()

    def _connect_to_db(self):
        database.initialize(SqliteDatabase(self.config["core"].get("database", "kochira.db"),
                                           threadlocals=True))
        logger.info("Opened database connection: %s", self.config["core"]["database"])

        ACLEntry.create_table(True)

    def _connect_to_irc(self):
        self.networks = {}

        for network, config in self.config["networks"].items():
            client = Client(self, network, config["nickname"])
            client.connect(hostname=config["hostname"], port=config.get("port"),
                           password=config.get("password"),
                           channels=config.get("channels", []))
            self.networks[network] = client

        self.pool = ClientPool(self.networks.values())
        self.pool.handle_forever()

    def _load_services(self):
        for service, config in self.config["services"].items():
            if config.get("autoload"):
                try:
                    self.load_service(service)
                except:
                    pass # it gets logged


    def _shutdown_service(self, service):
        service.run_shutdown(self, service.storage_for(self))
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
        storage = Expando()

        try:
            module = importlib.import_module(name)

            if reload:
                module = imp.reload(module)

            if not hasattr(module, "service"):
                raise RuntimeError("{} is not a valid service".format(name))

            service = module.service
            self.services[service.name] = (service, storage)

            service.run_setup(self, storage)
        except:
            logger.error("Couldn't load service %s", name, exc_info=True)
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

    def run_hooks(self, hook, client, *args):
        """
        Attempt to dispatch a command to all command handlers.
        """

        for service, _ in list(self.services.values()):
            service.run_hooks(hook, client, *args)

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
