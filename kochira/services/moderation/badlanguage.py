"""
Bad language filtering.

Kick people for using bad languages.
"""

import re
import requests

from kochira import config
from kochira.service import Service, Config

service = Service(__name__, __doc__)

CONTROL_CODE_RE = re.compile(
    "\x1f|\x02|\x12|\x0f|\x16|\x03(?:\d{1,2}(?:,\d{1,2})?)?", re.UNICODE)

def strip_control_codes(s):
    return CONTROL_CODE_RE.sub("", s)


@service.config
class Config(Config):
    languages = config.Field(doc="Language codes to ban.", type=config.Many(str))
    api_key = config.Field(doc="API key for detectlanguage.com")
    kick_message = config.Field(doc="Kick message.", default="Watch your language!")


@service.hook("channel_message", priority=2500)
def check_bad_languages(ctx, target, origin, message):
    resp = requests.get("http://ws.detectlanguage.com/0.2/detect", params={"q": message, "key": ctx.config.api_key}).json()
    raise Exception(resp)
    if any(detection in ctx.config.languages for detection in resp["data"]["detections"] if detection["isReliable"]):
        ctx.client.rawmsg("KICK", ctx.target, ctx.origin, ctx.config.kick_message)
        return Service.EAT
