import logging
from pydle import Client

from .auth import ACLEntry

logger = logging.getLogger(__name__)


class Client(Client):
    def __init__(self, bot, network, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.bot = bot

        # set network name to whatever we have in our config
        self.network = network

    def has_permission(self, hostmask, permission, channel=None):
        """
        Check if a hostmask has a given permission.
        """
        return ACLEntry.has(hostmask, self.network, permission, channel)

    def grant_permission(self, hostmask, permission, channel=None):
        """
        Grant a permission to a hostmask.
        """
        ACLEntry.grant(hostmask, self.network, permission, channel)

    def revoke_permission(self, hostmask, permission, channel):
        """
        Revoke a permission from a hostmask.
        """
        ACLEntry.revoke(hostmask, self.network, permission, channel)

    def on_connect(self):
        logger.info("Connected to IRC network: %s", self.network)
        super().on_connect()

    def on_message(self, target, origin, message):
        self.bot.run_hooks("message", self, target, origin, message)
