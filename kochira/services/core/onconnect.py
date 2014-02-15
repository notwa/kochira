"""
Run IRC commands on connect.

This allows the bot to run IRC commands on connection.
"""

from kochira import config
from kochira.service import Service, Config

service = Service(__name__, __doc__)


@service.config
class Config(Config):
    commands = config.Field(doc="List of commands to run.",
                            type=config.Many(list))


@service.hook("connect", priority=-10)
def onconnect(client):
    config = service.config_for(client.bot, client.name)

    for command in config.commands:
        client.rawmsg(*command)
