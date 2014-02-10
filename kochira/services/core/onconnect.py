"""
Run IRC commands on connect.

This allows the bot to run IRC commands on connection.
"""

from kochira import config
from kochira.service import Service, Config

service = Service(__name__, __doc__)


@service.config
class Config(Config):
    networks = config.Field(doc="Mapping of networks, filled with lists of raw commands.",
                            type=config.Mapping(config.Many(str)))


@service.hook("connect", priority=-10)
def onconnect(client):
    config = service.config_for(client.bot, client.network)

    for command in config.networks.get(client.network, []):
        client.raw(command)
