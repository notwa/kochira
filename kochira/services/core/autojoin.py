"""
Autojoin channels on connect.

This allows the bot to automatically join channels when it connects.

Configuration Options
=====================

``networks``
  A dictionary of networks, with network name as key and the list of channels
  as value, e.g. ``{"freenode": [{"name": "#kochira"}]}``.

  If a password is required to join the channel, the key `"password"` can be
  in the dictionary.

Commands
========
None.
"""

from kochira.service import Service

service = Service(__name__, __doc__)


@service.hook("connect")
def autojoin(client):
    config = service.config_for(client.bot)

    for channel in config.get("networks", {}).get(client.network, []):
        client.join(channel["name"], password=channel.get("password"))
