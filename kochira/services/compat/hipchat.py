"""
Hipchat support.

Translate user IDs to @mention names.
"""

import requests
import ccy
import time

from kochira import config
from kochira.service import Service, background, Config

service = Service(__name__, __doc__)


@service.config
class Config(Config):
    enabled = config.Field(doc="Whether or not this service is enabled (false by default).", default=False)
    auth_token = config.Field(doc="HipChat authentication token.")


@service.setup
def initialize_storage(ctx):
    ctx.storage.users = {}


def _update_users(auth_token, storage):
    req = requests.get("https://api.hipchat.com/v1/users/list",
                       params={"auth_token": auth_token})
    req.raise_for_status()

    users = {}

    for user in req.json()["users"]:
        users[user["user_id"]] = user["mention_name"]

    storage.users = users


@service.hook("respond")
@background
def translate_mention(ctx, target, origin, message):
    _, user_id = ctx.client.users[origin].username.split("_")
    user_id = int(user_id)

    if user_id not in ctx.storage.users:
        _update_users(ctx.config.auth_token, ctx.storage)

    origin = ctx.storage.users.get(user_id, origin)

    ctx.message(ctx.client.config.response_format.format(
        origin=origin,
        message=message
    ))

    return Service.EAT
