"""
Passive-aggressive spelling corrector.

Ensures that users are using Freedom English.
"""

import enchant
import re

from textblob import TextBlob
from nltk.corpus import wordnet

from kochira.service import Service, background

us_dic = enchant.Dict("en_US")
gb_dic = enchant.Dict("en_GB")

service = Service(__name__, __doc__)


def is_meaning_identical(gb, us):
    return bool(set(wordnet.synsets(gb)) - set(wordnet.synsets(us)))


def compute_replacements(message):
    blob = TextBlob(message)
    replacements = {}

    for word in blob.words:
        word = str(word)

        if (gb_dic.check(word) or any(word.lower() == s.lower() for s in gb_dic.suggest(word))) and \
            not (us_dic.check(word) or any(word.lower() == s.lower() for s in us_dic.suggest(word))):
            suggestions = [s for s in us_dic.suggest(word)
                           if s.lower() != word.lower() and is_meaning_identical(word, s)]

            if suggestions:
                replacements[word] = suggestions[0]

    return replacements


@service.hook("channel_message")
@background
def murrika(client, target, origin, message):
    replacements = compute_replacements(message)

    if not replacements:
        return

    for src, tgt in replacements.items():
        message = re.sub(r"\b{}\b".format(re.escape(src)),
                         "\x1f" + tgt + "\x1f", message)

    client.message(target, "<{origin}> {message}".format(
        origin=origin,
        message=message
    ))
