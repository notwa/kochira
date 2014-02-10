"""
Passive-aggressive spelling corrector.

Ensures that users are using Freedom English.
"""

import enchant
from textblob import TextBlob
from kochira.service import Service

us_dic = enchant.Dict("en_US")
gb_dic = enchant.Dict("en_GB")

service = Service(__name__, __doc__)


def compute_replacements(message):
    blob = TextBlob(message)
    replacements = {}

    for word in blob.words:
        word = str(word)

        if gb_dic.check(word) and not us_dic.check(word):
            suggestions = [s for s in us_dic.suggest(word)
                           if not any(c in "- " for c in s)]

            if suggestions:
                replacements[word] = suggestions[0]

    return replacements


@service.hook("channel_message")
def murrika(client, target, origin, message):
    replacements = compute_replacements(message)

    if not replacements:
        return

    for src, tgt in replacements.items():
        message = message.replace(src, "\x1f" + tgt + "\x1f")

    client.message(target, "<{origin}> {message}".format(
        origin=origin,
        message=message
    ))
