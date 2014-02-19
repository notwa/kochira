"""
Remote Cobe service.

Allows the bot to reply whenever its nickname is mentioned using a remote Cobe
brain.
"""

import random
import re

from kochira import config
from kochira.service import Service, background, Config
import requests

service = Service(__name__, __doc__)

@service.config
class Config(Config):
    url = config.Field(doc="The remote cobed to connect to.")
    username = config.Field(doc="The username to use when connecting.")
    password = config.Field(doc="The password to use when connecting.")
    reply = config.Field(doc="Whether or not to generate replies.", default=True)
    random_replyness = config.Field(doc="Probability the brain will generate a reply for all messages.", default=0.0)


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
def do_reply(ctx, target, origin, message):
    front, _, rest = message.partition(" ")

    mention = False
    reply = False

    if front.startswith('?'):
        reply = True
        message = front.lstrip('?') + ' ' + rest
    elif front.strip(",:").lower() == ctx.client.nickname.lower():
        mention = True
        reply = True
        message = rest
    elif random.random() < ctx.config.random_replyness:
        reply = True

    message = message.strip()

    if re.search(r"\b{}\b".format(re.escape(ctx.client.nickname)), message, re.I) is not None:
        reply = True

    if reply and ctx.config.reply:
        reply_message = reply_and_learn(ctx.config.url,
                                        ctx.config.username,
                                        ctx.config.password,
                                        message)

        if mention:
            ctx.respond(reply_message)
        else:
            ctx.message(reply_message)
    elif message:
        learn(ctx.config.url, ctx.config.username, ctx.config.password, message)

