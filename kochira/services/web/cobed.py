"""
Remote Cobe service.

Allows the bot to reply whenever its nickname is mentioned using a remote Cobe
brain.

Configuration Options
=====================

``brain_file``
  Location to store the brain in.

``username``
  Username for cobed.

``password``
  Password for cobed.

Commands
========
None.
"""

import re

from kochira.service import Service, background
import requests

service = Service(__name__, __doc__)


def reply_and_learn(url, username, password, what):
    return requests.post(url,
                        params={"q": what},
                        headers={"X-Cobed-Auth": username + ":" + password}) \
        .text

def learn(url, username, password, what):
    requests.post(url,
                  params={"q": what, "n": False},
                  headers={"X-Cobed-Auth": username + ":" + password})


@service.hook("channel_message", priority=-9999)
@background
def do_reply(client, target, origin, message):
    config = service.config_for(client.bot)

    front, _, rest = message.partition(" ")

    mention = False
    reply = False

    if front.strip(",:").lower() == client.nickname.lower():
        mention = True
        reply = True
        message = rest

    message = message.strip()

    if re.search(r"\b{}\b".format(re.escape(client.nickname)), message, re.I) is not None:
        reply = True

    if reply:
        reply_message = reply_and_learn(config["url"],
                                        config["username"],
                                        config["password"],
                                        message)

        if mention:
            client.message(target, "{origin}: {message}".format(origin=origin, message=reply_message))
        else:
            client.message(target, reply_message)
    elif message:
        learn(config["url"],
              config["username"],
              config["password"],
              message)

