import os
import glob
import requests
import tempfile
import subprocess

from datetime import timedelta
from pysnap import Snapchat, MEDIA_VIDEO_NOAUDIO, MEDIA_VIDEO

from ..service import Service

service = Service(__name__)

GIF_FRAMERATE = 7
GIF_MAX_LENGTH = 360

def convert_to_gif(blob):
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "video.mp4"), "wb") as f:
            f.write(blob)

        if subprocess.call(["ffmpeg", "-i", os.path.join(d, "video.mp4"),
                            "-vf", "scale=\"'if(gt(a,{aspect}),{max_length},-1)':'if(gt(a,{aspect}),-1,{max_length})'\"".format(
                                aspect="16/9",
                                max_length=GIF_MAX_LENGTH
                            ),
                            "-r", str(GIF_FRAMERATE),
                            os.path.join(d, "frames%03d.gif")]) != 0:
            return None

        if subprocess.call(["gifsicle", "--delay={}".format(100 // GIF_FRAMERATE),
                            "--loop", "-o",
                            os.path.join(d, "out.gif"), "-O"] +
                            sorted(glob.glob(os.path.join(d, "frames[0-9][0-9][0-9].gif")))) != 0:
            return None

        with open(os.path.join(d, "out.gif"), "rb") as f:
            return f.read()


@service.setup
def make_snapchat(bot, storage):
    config = service.config_for(bot)

    storage.snapchat = Snapchat()
    if not storage.snapchat.login(config["username"],
                                  config["password"]).get("logged"):
        raise Exception("could not log into Snapchat")


@service.task(interval=timedelta(seconds=30))
def poll_for_updates(bot):
    config = service.config_for(bot)
    storage = service.storage_for(bot)

    has_snaps = False

    for snap in reversed(storage.snapchat.get_snaps()):
        has_snaps = True
        sender = snap["sender"]

        blob = storage.snapchat.get_blob(snap["id"])
        if blob is None:
            continue

        if snap["media_type"] in (MEDIA_VIDEO, MEDIA_VIDEO_NOAUDIO):
            blob = convert_to_gif(blob)

        if blob is not None:
            ulim = requests.post("https://api.imgur.com/3/upload.json",
                                 headers={"Authorization": "Client-ID " + config["imgur_clientid"]},
                                 data={"image": blob}).json()
            if ulim["status"] != 200:
                link = "(unavailable)"
            else:
                link = ulim["data"]["link"]
        else:
            link = "(could not convert video)"

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
