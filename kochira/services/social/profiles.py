"""
Personal profiles.

This service allows the bot to keep track of people's profiles.
"""

from pydle.async import blocking

from kochira.service import Service
from kochira.userdata import UserData

service = Service(__name__, __doc__)


@service.command(r"forget(?: about)? me$", mention=True)
def forget_profile(client, target, origin):
    """
    Forget profile.

    Remove the given profile text from the user.
    """

    try:
        user_data = yield UserData.lookup(client, origin)
    except UserData.DoesNotExist:
        exists = False
    else:
        exists = "profile" in user_data

    if not exists:
        client.message(target, "{origin}: I don't know who you are.".format(
            origin=origin
        ))
        return

    del user_data["profile"]

    client.message(target, "{origin}: Okay, I won't remember you anymore.".format(
        origin=origin
    ))


@service.command(r"[Ii](?: a|')m (?P<text>.+)$", mention=True)
@blocking
def remember_profile(client, target, origin, text):
    """
    Remember profile.

    Associate the given profile text with the user.
    """

    try:
        user_data = yield UserData.lookup(client, origin)
    except UserData.DoesNotExist:
        client.message(target, "{origin}: Please authenticate before you add a profile.".format(
            origin=origin
        ))
        return

    user_data["profile"] = text

    client.message(target, "{origin}: Okay, I'll remember you.".format(
        origin=origin
    ))


@service.command(r"who am [Ii]\??$", mention=True)
@service.command(r"who(?: is|'s| the .* is) (?P<who>\S+)\??$", mention=True)
@blocking
def get_profile(client, target, origin, who=None):
    """
    Get profile.

    Retrieve profile text for a user.
    """
    if who is None:
        who = origin

    user_data = yield UserData.lookup_default(client, who)

    if "profile" not in user_data:
        client.message(target, "{origin}: {who} hasn't told me who they are yet.".format(
            origin=origin,
            who=who
        ))
        return

    client.message(target, "{origin}: {who} is {text}".format(
        origin=origin,
        who=who,
        text=user_data["profile"]
    ))
