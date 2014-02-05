from ..service import Service

service = Service(__name__)


@service.hook("connect")
def autojoin(client):
    config = service.config_for(client.bot)

    for channel in config.get("networks", {}).get(client.network, []):
        client.join(channel)
