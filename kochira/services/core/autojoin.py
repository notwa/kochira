"""
Autojoin channels on connect.

This allows the bot to automatically join channels when it connects.
"""

from kochira import config
from kochira.service import Service, Config

service = Service(__name__, __doc__)


@service.config
class Config(Config):
    class Channel(config.Config):
        name = config.Field(doc="The name of a network.")
        password = config.Field(doc="The key to a network, if any.",
                                default=None)

    channels = config.Field(doc="List of channels to join.",
                            type=config.Many(Channel))


@service.hook("connect", priority=-10)
def autojoin(client):
    config = service.config_for(client.bot, client.network)

    for channel in config.channels:
        client.join(channel.name, password=channel.password)
