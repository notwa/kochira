"""
Artificial (un)intelligence.

Allows the bot to reply whenever its nickname is mentioned.

Configuration Options
=====================

``brain_file``
  Location to store the brain in.

Commands
========
None.
"""

import re

from kochira.service import Service, background
from cobe.brain import Brain

service = Service(__name__, __doc__)


@service.setup
def load_brain(bot):
    config = service.config_for(bot)
    storage = service.storage_for(bot)

    storage.brain = Brain(config["brain_file"], check_same_thread=False)


@service.shutdown
def unload_brain(bot):
    storage = service.storage_for(bot)

    storage.brain.graph.close()


@service.hook("channel_message", priority=-9999)
@background
def reply_and_learn(client, target, origin, message):
    storage = service.storage_for(client.bot)

    front, _, rest = message.partition(" ")

    mention = False
    reply = False

    if front.strip(",:").lower() == client.nickname:
        mention = True
        reply = True
        message = rest

    message = message.strip()

    if re.search(r"\b{}\b".format(re.escape(client.nickname)), message, re.I) is not None:
        reply = True

    if reply:
        reply_message = storage.brain.reply(message)

        if mention:
            client.message(target, "{origin}: {message}".format(origin=origin, message=reply_message))
        else:
            client.message(target, reply_message)

    if message:
        storage.brain.learn(message)
