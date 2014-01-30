import requests
import time

from datetime import timedelta
from pysnap import Snapchat

from ..service import Service

service = Service(__name__)


@service.register_setup
def make_snapchat(bot, storage):
    config = service.config_for(bot)

    storage.snapchat = Snapchat()
    if not storage.snapchat.login(config["username"],
                                  config["password"]).get("logged"):
        raise Exception("could not log into Snapchat")


@service.register_task(interval=timedelta(seconds=30))
def poll_for_updates(bot):
    config = service.config_for(bot)
    storage = service.storage_for(bot)

    has_snaps = False

    for snap in reversed(storage.snapchat.get_snaps(time.time() - 60)):
        has_snaps = True
        sender = snap["sender"]

        blob = storage.snapchat.get_blob(snap["id"])
        if blob is None:
            continue

        ulim = requests.post("https://api.imgur.com/3/upload.json",
                             headers={"Authorization": "Client-ID " + config["imgur_clientid"]},
                             data={"image": blob}).json()

        if ulim["status"] != 200:
            link = "(unavailable)"
        else:
            link = ulim["data"]["link"]

        storage.snapchat.mark_viewed(snap["id"])

        for announce in config["announce"]:
            bot.networks[announce["network"]].message(
                announce["channel"],
                "New snap from {sender}! {link}".format(
                    sender=sender,
                    link=link
                )
            )

    if has_snaps:
        storage.snapchat._request("clear", {
            "username": storage.snapchat.username
        })
