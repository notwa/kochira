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


@service.model
class Reminder(Model):
    message = TextField()
    origin = CharField(255)
    who = CharField(255)
    who_n = CharField(255)
    channel = CharField(255)
    client_name = CharField(255)
    ts = DateTimeField()
    duration = IntegerField(null=True)


@service.setup
def reschedule_reminders(ctx):
    for reminder in Reminder.select() \
        .where(~(Reminder.duration >> None)):
        dt = (reminder.ts + timedelta(seconds=reminder.duration)) - datetime.utcnow()

        if dt < timedelta(0):
            reminder.delete_instance()
            continue

        ctx.bot.scheduler.schedule_after(dt, play_timed_reminder, reminder)


@service.task
def play_timed_reminder(ctx, reminder):
    needs_archive = False

    if reminder.client_name in ctx.bot.clients:
        client = ctx.bot.clients[reminder.client_name]

        if reminder.channel in client.channels:
            if reminder.who in client.channels[reminder.channel]["users"]:
                client.message(reminder.channel, ctx._("{who}: {origin} wanted you to know: {message}").format(
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


@service.command(r"(?:remind|tell) (?P<who>\S+) (?:about|to|that) (?P<message>.+) (?P<duration>(?:in|on|after) .+|at .+|tomorrow)$", mention=True, priority=1)
@service.command(r"(?:remind|tell) (?P<who>\S+) (?P<duration>(?:in|on|after) .+|at .+|tomorrow) (?:about|to|that) (?P<message>.+)$", mention=True, priority=1)
def add_timed_reminder(ctx, who, duration, message):
    """
    Add timed reminder.

    Add a reminder that will play after `time` has elapsed. If the user has left
    the channel, the reminder will play as soon as they return.
    """

    now = datetime.now()
    t = parse_time(duration)

    if who.lower() == "me" and who not in ctx.client.channels[ctx.target]["users"]:
        who = ctx.origin

    if t is None:
        ctx.respond(ctx._("Sorry, I don't understand that time."))
        return

    dt = timedelta(seconds=int(math.ceil((parse_time(duration) - now).total_seconds())))

    if dt < timedelta(0):
        ctx.respond(ctx._("Uh, that's in the past."))
        return

    # persist reminder to the DB
    reminder = Reminder.create(who=who, who_n=ctx.client.normalize(who),
                               channel=ctx.target, origin=ctx.origin,
                               message=message, client_name=ctx.client.name,
                               ts=datetime.utcnow(),
                               duration=dt.total_seconds())
    reminder.save()

    ctx.respond(ctx._("Okay, I'll let {who} know in around {dt}.").format(
        who=who,
        dt=humanize.naturaltime(-dt)
    ))

    # ... but also schedule it
    ctx.bot.scheduler.schedule_after(dt, play_timed_reminder, reminder)


@service.command(r"(?:remind|tell) (?P<who>\S+)(?: about| to| that)? (?P<message>.+)$", mention=True)
def add_reminder(ctx, who, message):
    """
    Add reminder.

    Add a reminder that will play when the user joins the channel or next speaks on
    the channel.
    """

    if who.lower() == "me" and who not in ctx.client.channels[ctx.target]["users"]:
        who = ctx.origin

    Reminder.create(who=who, who_n=ctx.client.normalize(who),
                    channel=ctx.target, origin=ctx.origin, message=message,
                    client_name=ctx.client.name, ts=datetime.utcnow(),
                    duration=None).save()

    ctx.respond(ctx._("Okay, I'll let {who} know.").format(
        who=who
    ))


@service.hook("channel_message")
def play_reminder_on_message(ctx, target, origin, message):
    play_reminder(ctx, ctx.target, ctx.origin)


@service.hook("join")
def play_reminder_on_join(ctx, channel, user):
    play_reminder(ctx, channel, user)


def play_reminder(ctx, target, origin):
    now = datetime.utcnow()
    origin = ctx.client.normalize(origin)

    for reminder in Reminder.select().where(Reminder.who_n == origin,
                                            Reminder.channel == target,
                                            Reminder.client_name == ctx.client.name,
                                            Reminder.duration >> None) \
        .order_by(Reminder.ts.asc()):

        # TODO: display time
        dt = now - reminder.ts

        ctx.message(ctx._("{who}, {origin} wanted you to know: {message}").format(
            who=reminder.who,
            origin=reminder.origin,
            message=reminder.message
        ))

    Reminder.delete().where(Reminder.who_n == origin,
                            Reminder.channel == target,
                            Reminder.client_name == ctx.client.name,
                            Reminder.duration >> None).execute()
