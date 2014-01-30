import parsedatetime

from datetime import datetime, timedelta
from peewee import TextField, CharField, DateTimeField, IntegerField

import math

from ..db import Model

from ..service import Service

service = Service(__name__)

cal = parsedatetime.Calendar()


def parse_time(s):
    result, what = cal.parse(s)

    dt = None

    if what in (1,  2):
        dt = datetime(*result[:6])
    elif what == 3:
        dt = result

    return dt

class Reminder(Model):
    message = TextField()
    origin = CharField(255)
    who = CharField(255)
    channel = CharField(255)
    network = CharField(255)
    ts = DateTimeField()
    duration = IntegerField(null=True)


@service.setup
def initialize_model(bot, storage):
    Reminder.create_table(True)

    for reminder in Reminder.select() \
        .where(~(Reminder.duration >> None)):
        dt = datetime.utcnow() - (reminder.ts + timedelta(seconds=reminder.duration))
        bot.scheduler.schedule_after(dt, play_timed_reminder, reminder)


@service.task
def play_timed_reminder(bot, reminder):
    if reminder.network in bot.networks:
        bot.networks[reminder.network].message(reminder.channel, "{who}, {origin} wanted you to know: {message}".format(
            who=reminder.who,
            origin=reminder.origin,
            message=reminder.message
        ))

    reminder.delete_instance()


@service.command(r"remind (?P<who>\S+)(?: about| to| that)? (?P<message>.+) (?P<duration>(?:in|after) .+)$", mention=True)
@service.command(r"remind (?P<who>\S+) (?P<duration>(?:in|after) .+) (?:about|to|that) (?P<message>.+)$", mention=True)
def add_timed_reminder(client, target, origin, who, duration, message):
    now = datetime.now()
    t = parse_time(duration)

    if t is None:
        client.message(target, "{origin}: Sorry, I don't understand that time.".format(
            origin=origin
        ))
        return

    dt = timedelta(seconds=int(math.ceil((parse_time(duration) - now).total_seconds())))

    if dt < timedelta(0):
        client.message(target, "{origin}: Uh, that's in the past.".format(
            origin=origin
        ))
        return

    # persist reminder to the DB
    reminder = Reminder.create(who=who, channel=target, origin=origin,
                               message=message, network=client.network,
                               ts=datetime.utcnow(),
                               duration=dt.total_seconds())
    reminder.save()

    client.message(target, "{origin}: Okay, I'll let {who} know in {dt}.".format(
        origin=origin,
        who=who,
        dt=dt
    ))

    # ... but also schedule it
    client.bot.scheduler.schedule_after(dt, play_timed_reminder, reminder)


@service.command(r"tell (?P<who>\S+)(?: about| to| that)? (?P<message>.+)$", mention=True)
def add_reminder(client, target, origin, who, message):
    Reminder.create(who=who, channel=target, origin=origin, message=message,
                    network=client.network, ts=datetime.utcnow(),
                    duration=None).save()

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
                                            Reminder.network == client.network,
                                            Reminder.duration >> None) \
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
                            Reminder.network == client.network,
                            Reminder.duration >> None).execute()
