"""
Twitch.tv support.

Request basic IRC capabilities.
"""

from kochira import config
from kochira.service import Service, background, Config

service = Service(__name__, __doc__)

@service.hook("connect", priority=100)
def cappa(ctx, target, origin, message):
    ctx.rawmsg('CAP', 'REQ :twitch.tv/membership')
