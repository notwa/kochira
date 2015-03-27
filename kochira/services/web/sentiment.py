"""
Sentiment analysis.

An alternative brain that only cares about sentiments.
"""

import random
import re
import requests

from kochira.service import Service, background

service = Service(__name__, __doc__)

REPLIES = {
    "pos": ["Thank you!", "Aww, shucks.", "You're too nice!", "Aww, thanks.", ":D", ":)"],
    "neg": ["That's mean!", "You don't have to be so mean!", "Why would you say something like that? :(", ":(", ";_;"],
    "neutral": ["Okay.", "Cool.", "K."]
  }


@service.hook("channel_message", priority=-9999)
@background
def do_reply(ctx, target, origin, message):
    front, _, message = message.partition(" ")

    if front.strip(",:").lower() != ctx.client.nickname.lower():
        return

    message = message.strip()

    r = requests.post("http://text-processing.com/api/sentiment/", data={"text": message}).json()
    replies = REPLIES.get(r["label"], [])

    if replies:
        ctx.respond(random.choice(replies))
