"""
Unicode character database.

Identify unicode characters.
"""

import unicodedata

from kochira.service import Service

service = Service(__name__, __doc__)


@service.command(r"!u (?P<character>.)", re_flags=0)
def query(ctx, character):
    """
    Query.

    Find information about a Unicode character.
    """

    try:
        name = unicodedata.name(character)
    except ValueError:
        ctx.respond(ctx._("I don't know what that character is."))
        return

    category = unicodedata.category(character)

    ctx.respond(ctx._("{character} (0x{hex}): {name} (Category: {category})").format(
        character=character,
        hex=hex(ord(character)),
        name=name,
        category=category
    ))


@service.command(r"!U (?P<name>.+)", re_flags=0)
def lookup(ctx, name):
    """
    Lookup.

    Lookup a Unicode character by name.
    """

    name = name.upper()

    try:
        character = unicodedata.lookup(name)
    except ValueError:
        ctx.respond(ctx._("I don't know what that character is."))
        return

    category = unicodedata.category(character)

    ctx.respond(ctx._("{character} (0x{hex}): {name} (Category: {category})").format(
        character=character,
        hex=hex(ord(character)),
        name=name,
        category=category
    ))

