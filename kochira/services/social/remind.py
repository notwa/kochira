"""
Timed and join reminders.

Enables the bot to record and play reminders after timed intervals or on user
join.
"""

import humanize
import parsedatetime

from datetime import datetime, timedelta
from peewee import TextField, CharField, DateTimeField, IntegerField

import math

from kochira.db import Model

from kochira.service import Service

service = Service(__name__, __doc__)

cal = parsedatetime.Calendar()


def parse_time(s):
    result, what = cal.parse(s)

    dt = None

    if what in (1, 2):
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
def initialize_model(bot):
    Reminder.create_table(True)

    for reminder in Reminder.select() \
        .where(~(Reminder.duration >> None)):
        dt = (reminder.ts + timedelta(seconds=reminder.duration)) - datetime.utcnow()

        if dt < timedelta(0):
            reminder.delete_instance()
            continue

        bot.scheduler.schedule_after(dt, play_timed_reminder, reminder)


@service.task
def play_timed_reminder(bot, reminder):
    needs_archive = False

    if reminder.network in bot.networks:
        client = bot.networks[reminder.network]

        if reminder.channel in client.channels:
            if reminder.who in client.channels[reminder.channel]["users"]:
                client.message(reminder.channel, "{who}, {origin} wanted you to know: {message}".format(
                    who=reminder.who,
                    origin=reminder.origin,
                    message=reminder.message
                ))
            else:
                needs_archive = True
                reminder.duration = None
                reminder.save()

    if not needs_archive:
        reminder.delete_instance()


@service.command(r"(?:remind|tell) (?P<who>\S+) (?:about|to|that) (?P<message>.+) (?P<duration>(?:in|after) .+|tomorrow)$", mention=True)
@service.command(r"(?:remind|tell) (?P<who>\S+) (?P<duration>(?:in|after) .+|tomorrow) (?:about|to|that) (?P<message>.+)$", mention=True)
def add_timed_reminder(client, target, origin, who, duration, message):
    """
    Add timed reminder.

    Add a reminder that will play after `time` has elapsed. If the user has left
    the channel, the reminder will play as soon as they return.
    """

    now = datetime.utcnow()
    t = parse_time(duration)

    if who.lower() == "me" and who not in client.channels[target]["users"]:
        who = origin

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

    client.message(target, "{origin}: Okay, I'll let {who} know in around {dt}.".format(
        origin=origin,
        who=who,
        dt=humanize.naturaltime(-dt)
    ))

    # ... but also schedule it
    client.bot.scheduler.schedule_after(dt, play_timed_reminder, reminder)


@service.command(r"(?:remind|tell) (?P<who>\S+)(?: about| to| that)? (?P<message>.+)$", mention=True)
def add_reminder(client, target, origin, who, message):
    """
    Add reminder.

    Add a reminder that will play when the user joins the channel or next speaks on
    the channel.
    """

    if who.lower() == "me" and who not in client.channels[target]["users"]:
        who = origin

    Reminder.create(who=who, channel=target, origin=origin, message=message,
                    network=client.network, ts=datetime.utcnow(),
                    duration=None).save()

    client.message(target, "{origin}: Okay, I'll let {who} know.".format(
        origin=origin,
        who=who
    ))


@service.hook("channel_message")
def play_reminder_on_message(client, target, origin, message):
    play_reminder(client, target, origin)


@service.hook("join")
def play_reminder_on_join(client, channel, user):
    play_reminder(client, channel, user)


def play_reminder(client, target, origin):
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
