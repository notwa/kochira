"""
Topic queuing.

Enables users to add text to the topic via a queue of items.
"""

from kochira import config
from kochira.auth import requires_permission
from kochira.service import Service, Config

from pydle.features.rfc1459.protocol import TOPIC_LENGTH_LIMIT


service = Service(__name__, __doc__)

@service.config
class Config(Config):
    topic_separator = config.Field(doc="Separator to use between topic items.", default=" | ")


@service.command("add (?P<topic>.+) to topic", mention=True)
@service.command(".topic (?P<topic>.+)")
@requires_permission("topic")
def topic(client, target, origin, topic):
    config = service.config_for(client.bot, client.name, target)

    parts = client.channels[target].get("topic")

    if parts:
        parts = parts.split(config.topic_separator)
    else:
        parts = []

    parts.insert(0, topic)

    while len(config.topic_separator.join(parts)) > TOPIC_LENGTH_LIMIT:
        parts.pop()

    client.topic(target, config.topic_separator.join(parts))
