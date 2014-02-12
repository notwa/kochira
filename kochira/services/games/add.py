"""
Add to a number.

Not actually a game.
"""

from peewee import IntegerField

from kochira.db import Model
from kochira.service import Service

service = Service(__name__, __doc__)


class Add(Model):
    number = IntegerField()


@service.setup
def initialize_models(bot):
    Add.create_table(True)


@service.command("add", mention=True)
@service.command("!add", mention=False)
def add(client, target, origin):
    try:
        a = Add.get()
    except Add.DoesNotExist:
        a = Add.create(number=0)
    a.number += 1
    a.save()

    client.message(target, "{origin}: Thanks, the number has been increased to {number}.".format(
        origin=origin,
        number=a.number
    ))
