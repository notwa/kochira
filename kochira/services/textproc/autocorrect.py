"""
Automatic corrections for keywords.

This service enables the bot to perform automatic corrections for given
keywords.
"""

import re
from peewee import CharField

from kochira.db import Model

from kochira.service import Service
from kochira.auth import requires_permission

service = Service(__name__, __doc__)


@service.model
class Correction(Model):
    what = CharField(255)
    correction = CharField(255)

    class Meta:
        indexes = (
            (("what",), True),
        )


def is_regex(what):
    return what[0] == "/" and what[-1] == "/"


@service.command(r"stop correcting (?P<what>.+)$", mention=True)
@service.command(r"don't correct (?P<what>.+)$", mention=True)
@service.command(r"remove correction for (?P<what>.+)$", mention=True)
@requires_permission("autocorrect")
def remove_correction(ctx, what):
    """
    Remove correction.

    Remove the correction for `what`.
    """

    if not Correction.select().where(Correction.what == what).exists():
        ctx.respond(ctx._("I'm not correcting \"{what}\".").format(
            what=what
        ))
        return

    Correction.delete().where(Correction.what == what).execute()

    ctx.respond(ctx._("Okay, I won't correct {what} anymore.").format(
        what=what if is_regex(what) else "\"" + what + "\""
    ))


def make_case_corrector(target):
    def _closure(original):
        if all(c.isupper() for c in original):
            return target.upper()

        if all(c.islower() for c in original):
            return target.lower()

        if original.title() == original:
            return target.title()

        if original.capitalize() == original:
            return target.capitalize()

        return target
    return lambda match: _closure(match.group(0))


@service.hook("channel_message")
def do_correction(ctx, target, origin, message):
    corrected = message

    for correction in Correction.select():
        if is_regex(correction.what):
            expr = correction.what[1:-1]
        else:
            expr = r"\b{}\b".format(re.escape(correction.what))
        corrected = re.sub(expr,
                           make_case_corrector("\x1f" + correction.correction + "\x1f"),
                           corrected, 0, re.I)

    if message != corrected:
        ctx.message(ctx._("<{origin}> {corrected}").format(
            origin=origin,
            corrected=corrected
        ))


@service.command(r"correct (?P<what>.+?) to (?P<correction>.+)$", mention=True)
@requires_permission("autocorrect")
def add_correction(ctx, what, correction):
    """
    Add correction.

    Add an automatic correction for whenever someone says `what`. `what` can be a
    regular expression delimited by ``/``, e.g. ``/^foo$/``.
    """

    if Correction.select().where(Correction.what == what).exists():
        ctx.respond(ctx._("I'm already correcting {what}.").format(
            what=what if is_regex(what) else "\"" + what + "\""
        ))
        return

    Correction.create(what=what, correction=correction).save()

    ctx.respond(ctx._("Okay, I'll correct {what}.").format(
        what=what if is_regex(what) else "\"" + what + "\""
    ))


@service.command(r"what do you correct\??$", mention=True)
@service.command(r"corrections\??$", mention=True)
def list_corrections(ctx):
    """
    List corrections.

    List all corrections the bot has registered.
    """

    ctx.respond(ctx._("I correct the following: {corrections}").format(
        corrections=", ".join(correction.what if is_regex(correction.what) else "\"" + correction.what + "\""
                              for correction in Correction.select().order_by(Correction.what))
    ))
