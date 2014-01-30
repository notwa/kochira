import requests
from urllib.parse import urlencode

from ..service import Service

service = Service(__name__)


@service.command(r"!ud (?P<term>.+?)(?: (?P<num>\d+))?$", mention=True, background=True)
@service.command(r"define (?P<term>.+?)(?: \((?P<num>\d+)\))?\??$", mention=True, background=True)
@service.command(r"what does (?P<term>.+) mean(?: \((?P<num>\d+)\))?\??$", mention=True, background=True)
def define(client, target, origin, term, num: int=None):
    r = requests.get("http://api.urbandictionary.com/v0/define?" + urlencode({
        "term": term
    })).json()

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

    client.message(target, "{origin}: {term}: {definition} ({num} of {total})".format(
        origin=origin,
        term=term,
        definition=r["list"][num]["definition"],
        num=num + 1,
        total=total
    ))
