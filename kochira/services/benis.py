import functools
import random
import re
import unicodedata

from ..service import Service

service = Service(__name__)


def benisify(s):
    return functools.reduce(lambda acc, f: f(acc), [
        lambda s: s.lower(),
        lambda s: unicodedata.normalize('NFKD', s),
        lambda s: s.replace('x', 'cks'),
        lambda s: re.sub(r'ing','in', s),
        lambda s: re.sub(r'you', 'u', s),
        lambda s: re.sub(r'oo', 'u', s),
        lambda s: re.sub(r'ck', 'g', s),
        lambda s: re.sub(r'(t+)(?=[aeiouys]|\b)', lambda x: 'd' * len(x.group(1)), s),
        lambda s: s.replace('p', 'b'),
        lambda s: re.sub(r'\bthe\b', 'da', s),
        lambda s: re.sub(r'\bc', 'g', s),
        lambda s: re.sub(r'\bis\b', 'are', s),
        lambda s: re.sub(r'c+(?![eiy])', 'g', s),
        lambda s: re.sub(r'[qk]+(?=[aeiouy]|\b)', 'g', s),
        lambda s: re.sub(r'([?!.]|$)+', lambda x: (x.group(0) * random.randint(2, 5)) + " " + "".join((":" * random.randint(1, 2)) + ("D" * random.randint(1, 4)) for _ in range(random.randint(2, 5))), s),
    ], s)


@service.command(r"!benis(?: (?P<text>.+))?$")
@service.command(r"benis(?: (?P<text>.+))?$", mention=True)
def benis(client, target, origin, text=None):
    if text is None:
        if len(client.backlogs[target]) == 1:
            return

        _, text = client.backlogs[target][1]

    text = benisify(text)

    client.message(target, "{origin}: {text}".format(
        origin=origin,
        text=text
    ))
