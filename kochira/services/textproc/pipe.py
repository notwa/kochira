"""
Pipable commands.

Allow the outputs of commands to be piped into each other.
"""

import types
import re
from kochira.client import Client
from kochira.service import Service, coroutine

service = Service(__name__, __doc__)


class BufferedClient(Client):
    def __init__(self, client):
        self.__dict__.update(client.__dict__)
        self.buffer = []

    def message(self, target, message):
        if message.startswith("\r\n: "):
            message = message[4:]
        self.buffer.append(message)


# From http://stackoverflow.com/questions/18092354/python-split-string-without-splitting-escaped-character
def split_unescape(s, delim, escape='\\', unescape=True):
    """
    >>> split_unescape('foo,bar', ',')
    ['foo', 'bar']
    >>> split_unescape('foo$,bar', ',', '$')
    ['foo,bar']
    >>> split_unescape('foo$$,bar', ',', '$', unescape=True)
    ['foo$', 'bar']
    >>> split_unescape('foo$$,bar', ',', '$', unescape=False)
    ['foo$$', 'bar']
    >>> split_unescape('foo$', ',', '$', unescape=True)
    ['foo$']
    """
    ret = []
    current = []
    itr = iter(s)
    for ch in itr:
        if ch == escape:
            try:
                # skip the next character; it has been escaped!
                if not unescape:
                    current.append(escape)
                current.append(next(itr))
            except StopIteration:
                if unescape:
                    current.append(escape)
        elif ch == delim:
            # split! (add current to the list and reset it)
            ret.append(''.join(current))
            current = []
        else:
            current.append(ch)
    ret.append(''.join(current))
    return ret


@service.command(r"!pipe (?P<commands>.+)")
@coroutine
def run_pipe(ctx, commands):
    """
    Run a pipe.

    Pipe commands into each other, e.g.::

        !pipe !quote rand | !benis _ | !topic _
    """

    parts = split_unescape(commands, "|")

    acc = ""

    parts.reverse()

    while parts:
        c = BufferedClient(ctx.client)
        message = re.sub(r"\b_\b", acc, parts.pop().strip())

        # \r\n is not allowed in the IRC protocol inside a message body, so we
        # use it as the prefix to strip off ctx.respond headers.
        yield c._run_hooks("channel_message", ctx.target, "\r\n",
                           [ctx.target, ctx.origin, message])
        acc = "\n".join(c.buffer)

    ctx.respond(acc)
