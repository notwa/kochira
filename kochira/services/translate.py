import requests
import pycountry
from urllib.parse import urlencode

from ..service import Service

service = Service(__name__)

LANGUAGES = {}

for language in pycountry.languages.objects:
    for name in language.name.split(";"):
        try:
            LANGUAGES[name.strip().lower()] = language.alpha2
        except AttributeError:
            continue


def perform_translation(term, sl, tl):
    return requests.get("http://translate.google.com/translate_a/t?" + urlencode({
        "client": "p",
        "sl": sl,
        "tl": tl,
        "text": term,
        "ie": "UTF-8",
        "oe": "UTF-8"
    })).json()


@service.command(r"(?:transliterate|romanize) (?P<term>.+?)(?: from (?P<from_lang>.+?))?$", mention=True, background=True)
def transliterate(client, target, origin, term, from_lang=None):
    if from_lang is None:
        sl = None
    else:
        try:
            sl = LANGUAGES.get(from_lang.lower())
        except KeyError:
            client.message(target, "{origin}: Sorry, I don't understand \"{lang}\".".format(
                    origin=origin,
                lang=from_lang
            ))
            return

    r = perform_translation(term, sl, sl)

    tlit = " ".join(x["src_translit"] for x in r["sentences"])

    if not tlit:
        client.message(target, "{origin}: There is no transliteration.".format(
            origin=origin
        ))
        return

    client.message(target, "{origin}: {sentences}".format(
        origin=origin,
        sentences=tlit
    ))


@service.command(r"what is (?P<term>.+) in (?P<to_lang>.+)\??$", mention=True, background=True)
@service.command(r"(?:translate) (?P<term>.+?)(?: from (?P<from_lang>.+?))?(?: to (?P<to_lang>.+))?$", mention=True, background=True)
def translate(client, target, origin, term, to_lang=None, from_lang=None):
    if from_lang is None:
        sl = "auto"
    else:
        try:
            sl = LANGUAGES.get(from_lang.lower())
        except KeyError:
            client.message(target, "{origin}: Sorry, I don't understand \"{lang}\".".format(
                origin=origin,
                lang=from_lang
            ))
            return

    if to_lang is None:
        tl = "en"
    else:
        try:
            tl = LANGUAGES.get(to_lang.lower())
        except KeyError:
            client.message(target, "{origin}: Sorry, I don't understand \"{lang}\".".format(
                origin=origin,
                lang=to_lang
            ))
            return

    r = perform_translation(term, sl, tl)

    client.message(target, "{origin}: {sentences}".format(
        origin=origin,
        sentences=" ".join(x["trans"] for x in r["sentences"])
    ))
