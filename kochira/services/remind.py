from datetime import datetime
from peewee import TextField, CharField, DateTimeField

from ..db import Model

from ..service import Service

service = Service(__name__)


class Reminder(Model):
    message = TextField()
    origin = CharField(255)
    who = CharField(255)
    channel = CharField(255)
    network = CharField(255)
    ts = DateTimeField()


@service.setup
def initialize_model(bot, storage):
    Reminder.create_table(True)


@service.command(r"tell (?P<who>\S+) (?P<message>.+)$", mention=True)
@service.command(r"remind (?P<who>\S+) (?P<message>.+)$", mention=True)
def add_reminder(client, target, origin, who, message):
    Reminder.create(who=who, channel=target, origin=origin, message=message,
                    network=client.network, ts=datetime.utcnow()).save()
    client.message(target, "{origin}: Okay, I'll let {who} know.".format(
        origin=origin,
        who=who
    ))


@service.hook("message")
@service.hook("join")
def play_reminder(client, target, origin, *_):
    now = datetime.utcnow()

    for reminder in Reminder.select().where(Reminder.who == origin,
                                            Reminder.channel == target,
                                            Reminder.network == client.network) \
        .order_by(Reminder.ts.asc()):

        # TODO: display time
        dt = now - reminder.ts

        client.message(target, "{who}, {origin} wanted you to know: {message}".format(
            who=reminder.who,
            origin=reminder.origin,
            message=reminder.message
        ))

    Reminder.delete().where(Reminder.who == origin,
                            Reminder.channel == target,
                            Reminder.network == client.network).execute()
