"""
Remote Cobe service.

Allows the bot to reply whenever its nickname is mentioned using a remote Cobe
brain.
"""

import random
import re

from kochira import config
from kochira.service import Service, background, Config
from kochira.services.social.loud import is_shout

import kochira.timeout as timeout

from websocket import create_connection


service = Service(__name__, __doc__)

@service.config
class Config(Config):
    url = config.Field(doc="The remote cobed to connect to.")
    reply = config.Field(doc="Whether or not to generate replies.", default=True)
    prefix = config.Field(doc="Prefix to trigger brain.", default="?")
    mention = config.Field(doc="Whether or not to mention activee.", default=True)
    ignore_caps = config.Field(doc="Skip over messages in all-caps.", default=True)
    random_replyness = config.Field(doc="Probability the brain will generate a reply for all messages.", default=0.0)
    timeout_messages, timeout_seconds, timeout_global = timeout.config()


@service.setup
def setup(ctx):
    timeout.setup(ctx)

def reply_and_learn(url, what):
    try:
        cobe = create_connection(url)
        cobe.send('?'+what)
        reply = cobe.recv()
        cobe.close()
        return reply
    except ConnectionRefusedError:
        pass


def learn(url, what):
    try:
        cobe = create_connection(url)
        cobe.send('!'+what)
        cobe.recv()
        cobe.close()
    except ConnectionRefusedError:
        pass


@service.hook("channel_message", priority=-9999)
@background
def do_reply(ctx, target, origin, message):
    front, _, rest = message.partition(" ")

    mention = False
    reply = False

    if ctx.config.prefix is not None and front.startswith(ctx.config.prefix):
        reply = True
        message = front[len(ctx.config.prefix):] + " " + rest
    elif front.strip(",:").lower() == ctx.client.nickname.lower():
        mention = True
        reply = True
        message = rest
    elif random.random() < ctx.config.random_replyness:
        reply = True

    message = message.strip()

    if re.search(r"\b{}\b".format(re.escape(ctx.client.nickname)), message, re.I) is not None:
        reply = True

    if reply and ctx.config.ignore_caps and is_shout(message):
        reply = False

    if reply and ctx.config.reply and timeout.handle(ctx, origin):
        reply_message = reply_and_learn(ctx.config.url, message)

        if reply_message is not None:
            if mention and ctx.config.mention:
                ctx.respond(reply_message)
            else:
                ctx.message(reply_message)
    elif message:
        learn(ctx.config.url, message)
