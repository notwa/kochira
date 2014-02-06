"""
UrbanDictionary lookup.

Retrieves definitions of terms from UrbanDictionary.

Configuration Options
=====================
None.

Commands
========

Define
------

::

    !ud <term>
    !ud <term> <num>
    $bot: define <term>
    $bot: define <term> (<num>)
    $bot: what does <term> mean?
    $bot: what does <term> (<num>) mean?

Look up the given term on UrbanDictionary.
"""

import requests

from kochira.service import Service, background

service = Service(__name__, __doc__)


@service.command(r"!ud (?P<term>.+?)(?: (?P<num>\d+))?$")
@service.command(r"define (?P<term>.+?)(?: \((?P<num>\d+)\))?\??$", mention=True)
@service.command(r"what does (?P<term>.+) mean(?: \((?P<num>\d+)\))?\??$", mention=True)
@background
def define(client, target, origin, term, num: int=None):
    r = requests.get("http://api.urbandictionary.com/v0/define", params={
        "term": term
    }).json()

    if r["result_type"] != "exact":
        client.message(target, "{origin}: I don't know what \"{term}\" means.".format(
            origin=origin,
            term=term
        ))
        return

    if num is None:
        num = 1

    # offset definition
    num -= 1
    total = len(r["list"])

    if num >= total or num < 0:
        client.message(target, "{origin}: Can't find that definition of \"{term}\".".format(
            origin=origin,
            term=term
        ))
        return

    client.message(target, "{origin}: {term}: {definition} ({num} of {total})".format(
        origin=origin,
        term=term,
        definition=r["list"][num]["definition"].replace("\r", "").replace("\n", " "),
        num=num + 1,
        total=total
    ))
