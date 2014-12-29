"""
Personal profiles.

This service allows the bot to keep track of people's profiles.
"""

from kochira.service import Service, coroutine
from kochira.userdata import UserData

service = Service(__name__, __doc__)


@service.command(r"forget(?: about)? me$", mention=True)
@service.command(r"!forget$", mention=False)
def forget_profile(ctx):
    """
    Forget profile.

    Remove the given profile text from the user.
    """

    try:
        user_data = yield ctx.lookup_user_data()
    except UserData.DoesNotExist:
        exists = False
    else:
        exists = "profile" in user_data

    if not exists:
        ctx.respond(ctx._("I don't know who you are."))
        return

    del user_data["profile"]
    user_data.save()

    ctx.respond(ctx._("Okay, I won't remember you anymore."))


@service.command(r"[Ii](?: a|')m (?P<text>.+)$", mention=True)
@service.command(r"!setinfo (?P<text>.+)$", mention=False)
@coroutine
def remember_profile(ctx, text):
    """
    Remember profile.

    Associate the given profile text with the user.
    """

    try:
        user_data = yield ctx.lookup_user_data()
    except UserData.DoesNotExist:
        ctx.respond(ctx._("Please authenticate before you add a profile."))
        return

    user_data["profile"] = text
    user_data.save()

    ctx.respond(ctx._("Okay, I'll remember you."))


@service.command(r"who am [Ii]\??$", mention=True)
@service.command(r"who(?: is|'s| the .* is) (?P<who>\S+?)\??$", mention=True)
@service.command(r"!info (?P<who>\S+?)$", mention=False)
@coroutine
def get_profile(ctx, who=None):
    """
    Get profile.

    Retrieve profile text for a user.
    """
    if who is None:
        who = ctx.origin

    user_data = yield UserData.lookup_default(ctx.client, who)

    if "profile" not in user_data:
        ctx.respond(ctx._("{who} hasn't told me who they are yet.").format(
            who=who
        ))
        return

    ctx.respond(ctx._("{who} is {text}").format(
        who=who,
        text=user_data["profile"]
    ))
