"""
Remote Cobe service.

Allows the bot to reply whenever its nickname is mentioned using a remote Cobe
brain.

Commands
========
None.
"""

import re

from kochira import config
from kochira.service import Service, background
import requests

service = Service(__name__, __doc__)

@service.config
class Config(config.Config):
    url = config.Field(doc="The remote cobed to connect to.")
    username = config.Field(doc="The username to use when connecting.")
    password = config.Field(doc="The password to use when connecting.")
    reply = config.Field(doc="Whether or not to reply on nickname mention.", default=True)

def reply_and_learn(url, username, password, what):
    r = requests.post(url,
                      params={"q": what},
                      headers={"X-Cobed-Auth": username + ":" + password})
    r.raise_for_status()
    return r.text


def learn(url, username, password, what):
    requests.post(url,
                  params={"q": what, "n": 1},
                  headers={"X-Cobed-Auth": username + ":" + password}) \
        .raise_for_status()


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

    if reply and config.reply:
        reply_message = reply_and_learn(config.url,
                                        config.username,
                                        config.password,
                                        message)

        if mention:
            client.message(target, "{origin}: {message}".format(origin=origin, message=reply_message))
        else:
            client.message(target, reply_message)
    elif message:
        learn(config.url, config.username, config.password, message)

