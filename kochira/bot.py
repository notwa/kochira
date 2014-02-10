from concurrent.futures import ThreadPoolExecutor

import collections
import functools
import imp
import importlib
import heapq
import logging
import multiprocessing
from peewee import SqliteDatabase
import signal
import yaml
from zmq.eventloop import ioloop

from . import config
from .auth import ACLEntry
from .client import Client
from .db import database
from .scheduler import Scheduler
from .util import Expando
from .service import Service

logger = logging.getLogger(__name__)


class BaseServiceConfig(config.Config):
    autoload = config.Field(doc="Autoload this service?", default=False)


class ServiceConfigLoader(collections.Mapping):
    def __init__(self, bot, values):
        self.bot = bot
        self.configs = values

    def _config_factory_for(self, name):
        if name not in self.bot.services:
            config_factory = BaseServiceConfig
        else:
            service, _ = self.bot.services[name]
            config_factory = service.config_factory
        return config_factory

    def __getitem__(self, name):
        return self._config_factory_for(name)(self.configs[name])

    def __iter__(self):
        return iter(self.configs)

    def __len__(self):
        return len(self.configs)


def _config_class_factory(bot):
    class Config(config.Config):
        class Network(config.Config):
            autoconnect = config.Field(doc="Whether or not to autoconnect to this network.", default=True)

            nickname = config.Field(doc="Nickname to use.")
            username = config.Field(doc="Username to use.", default=None)
            realname = config.Field(doc="Real name to use.", default=None)

            hostname = config.Field(doc="IRC server hostname.")
            port = config.Field(doc="IRC server port.", default=None)
            password = config.Field(doc="IRC server password.", default=None)
            source_address = config.Field(doc="Source address to connect from.", default="")

            class TLS(config.Config):
                enabled = config.Field(doc="Enable TLS?", default=False)
                verify = config.Field(doc="Verify TLS connection?", default=True)
                certificate_file = config.Field(doc="TLS certificate file.", default=None)
                certificate_keyfile = config.Field(doc="TLS certificate key file.", default=None)
                certificate_password = config.Field(doc="TLS certificate password.", default=None)

            class SASL(config.Config):
                username = config.Field(doc="SASL username.", default=None)
                password = config.Field(doc="SASL password.", default=None)

            tls = config.Field(doc="TLS settings.", type=TLS, default=TLS())
            sasl = config.Field(doc="SASL settings.", type=SASL, default=SASL())

        class Core(config.Config):
            database = config.Field(doc="Database file to use", default="kochira.db")
            max_backlog = config.Field(doc="Maximum backlog lines to store.", default=10)
            max_workers = config.Field(doc="Max thread pool workers.", default=0)
            version = config.Field(doc="CTCP VERSION reply.", default="kochira IRC bot")

        core = config.Field(doc="Core configuration settings.", type=Core)
        networks = config.Field(doc="Networks to connect to.", type=config.Mapping(Network))
        services = config.Field(doc="Services to load. Please refer to service documentation for setting this.", type=functools.partial(ServiceConfigLoader, bot))

    return Config


class Bot:
    """
    The core bot.
    """

    def __init__(self, config_file="config.yml"):
        self.services = {}
        self.networks = {}
        self.io_loop = ioloop.IOLoop()

        self.config_class = _config_class_factory(self)
        self.config_file = config_file

        self.rehash()
        self._connect_to_db()

    def run(self):
        self.executor = ThreadPoolExecutor(self.config.core.max_workers or multiprocessing.cpu_count())
        self.scheduler = Scheduler(self)
        self.scheduler.start()

        signal.signal(signal.SIGHUP, self._handle_sighup)

        self._load_services()
        self._connect_to_irc()

    def connect(self, network_name):
        config = self.config.networks[network_name]

        client = Client(self, network_name, config.nickname,
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

        self.networks[network_name] = client

        def handle_next_message(fd=None, events=None):
            if client._has_message():
                client.poll_single()
                self.io_loop.add_callback(handle_next_message)

        self.io_loop.add_handler(client.connection.socket.fileno(),
                                 handle_next_message,
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
        db_name = self.config.core.database
        database.initialize(SqliteDatabase(db_name, threadlocals=True))
        logger.info("Opened database connection: %s", db_name)

        ACLEntry.create_table(True)

    def _connect_to_irc(self):
        for network_name, config in self.config.networks.items():
            if config.autoconnect:
                self.connect(network_name)

        self.io_loop.start()

    def _load_services(self):
        for service, config in self.config.services.items():
            if config.autoload:
                try:
                    self.load_service(service)
                except:
                    pass # it gets logged

    def _shutdown_service(self, service):
        service.run_shutdown(self)
        self.scheduler.unschedule_service(service)

    def defer_from_thread(self, fn, *args, **kwargs):
        self.io_loop.add_callback(functools.partial(fn, *args, **kwargs))

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

    def get_hooks(self, hook):
        """
        Create an ordering of hooks to run.
        """

        return (hook for _, _, hook in heapq.merge(*[
            service.hooks.get(hook, [])
            for service, storage in list(self.services.values())
        ]))

    def run_hooks(self, hook, *args):
        """
        Attempt to dispatch a command to all command handlers.
        """

        for hook in self.get_hooks(hook):
            try:
                r = hook(*args)
                if r is Service.EAT:
                    return Service.EAT
            except BaseException:
                logger.error("Hook processing failed", exc_info=True)

    def rehash(self):
        """
        Reload configuration information.
        """

        with open(self.config_file, "r") as f:
            self.config = self.config_class(yaml.load(f))

    def _handle_sighup(self, signum, frame):
        logger.info("Received SIGHUP; running SIGHUP hooks and rehashing")

        try:
            self.rehash()
        except Exception as e:
            logger.error("Could not rehash configuration", exc_info=e)

        self.run_hooks("sighup", self)
