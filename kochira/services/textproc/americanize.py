"""
Passive-aggressive spelling corrector.

Ensures that users are using Freedom English. Could be configured for other
languages, I guess...
"""

import enchant
import re

from textblob import TextBlob
from nltk.corpus import wordnet

from kochira import config
from kochira.service import Service, background, Config

service = Service(__name__, __doc__)

DISSIMILARITY_THRESHOLD = 0.5

@service.config
class Config(Config):
    from_lang = config.Field(doc="Language to convert from.", default="en_GB")
    to_lang = config.Field(doc="Language to convert to (hint: en_US).", default="en_US")


def dissimilarity(from_word, to_word):
    from_syn = set(wordnet.synsets(from_word))
    to_syn = set(wordnet.synsets(to_word))

    both = from_syn & to_syn

    # we don't actually know anything about this word
    if not both:
        return float("inf")

    return len(from_syn - to_syn) / len(both)


def process_words(words):
    for word in words:
        # split hyphenated words because those suck
        yield from str(word).split("-")


def compute_replacements(from_lang, to_lang, message):
    from_dic = enchant.Dict(from_lang)
    to_dic = enchant.Dict(to_lang)

    blob = TextBlob(message)
    replacements = {}

    for word in process_words(blob.words):
        if (from_dic.check(word) or any(word.lower() == s.lower() for s in from_dic.suggest(word))) and \
            not (to_dic.check(word) or any(word.lower() == s.lower() for s in to_dic.suggest(word))):
            suggestions = sorted([(dissimilarity(word, s), i, s) for i, s in enumerate(to_dic.suggest(word))
                                  if s.lower() != word.lower()])
            if suggestions:
                score, _, replacement = suggestions[0]
                if score <= DISSIMILARITY_THRESHOLD:
                    replacements[word] = replacement

    return replacements


@service.hook("channel_message")
@background
def murrika(client, target, origin, message):
    config = service.config_for(client.bot, client.name, target)

    replacements = compute_replacements(config.from_lang, config.to_lang, message)

    if not replacements:
        return

    for src, tgt in replacements.items():
        message = re.sub(r"\b{}\b".format(re.escape(src)),
                         "\x1f" + tgt + "\x1f", message)

    client.message(target, "<{origin}> {message}".format(
        origin=origin,
        message=message
    ))
