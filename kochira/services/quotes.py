from datetime import datetime
from peewee import CharField, TextField, DateTimeField, fn
from ..db import Model

from ..service import Service
from ..auth import requires_permission

service = Service(__name__)


class Quote(Model):
    by = CharField(255)
    quote = TextField()
    channel = CharField(255)
    network = CharField(255)
    ts = DateTimeField()

    @property
    def as_text(self):
        return "Quote {id} by {by}: {quote}".format(
            id=self.id,
            by=self.by,
            quote=self.quote
        )


@service.setup
def initialize_model(bot, storage):
    Quote.create_table(True)


@service.command(r"add quote (?P<quote>.+)", mention=True)
@service.command(r"!quote add (?P<quote>.+)")
@requires_permission("quote")
def add_quote(client, target, origin, quote):
    quote = Quote.create(by=origin, quote=quote, channel=target,
                         network=client.network, ts=datetime.utcnow())
    quote.save()

    client.message(target, "{origin}: Added quote {qid}.".format(
        origin=origin,
        qid=quote.id
    ))


@service.command(r"[iI](?: am|'m)(?: very| quite| extremely) butthurt about quote (?P<qid>\d+)", mention=True)
@service.command(r"(?:destroy|remove|delete) quote (?P<qid>\d+)", mention=True)
@service.command(r"!quote del (?P<qid>\d+)")
@requires_permission("quote")
def delete_quote(client, target, origin, qid: int):
    if not Quote.select() \
        .where(Quote.id == qid,
               Quote.network == client.network,
               Quote.channel == target).exists():
        client.message(target, "{origin}: That's not a quote.".format(
            origin=origin
        ))

    Quote.delete().where(Quote.id == qid).execute()

    client.message(target, "{origin}: Deleted quote {qid}.".format(
        origin=origin,
        qid=qid
    ))


@service.command(r"what is quote (?P<qid>\d+)\??", mention=True)
@service.command(r"read quote (?P<qid>\d+)", mention=True)
@service.command(r"!quote read (?P<qid>\d+)")
def read_quote(client, target, origin, qid: int):
    q = Quote.select() \
        .where(Quote.id == qid,
               Quote.network == client.network,
               Quote.channel == target)

    if not q.exists():
        client.message(target, "{origin}: That's not a quote.".format(
            origin=origin
        ))

    quote = q[0]

    client.message(target, "{origin}: {quote}".format(
        origin=origin,
        quote=quote.as_text
    ))


@service.command(r"(?:give me a )?random quote", mention=True)
@service.command(r"!quote rand")
def rand_quote(client, target, origin):
    q = Quote.select() \
        .where(Quote.network == client.network, Quote.channel == target) \
        .order_by(fn.Random()) \
        .limit(1)

    if not q.exists():
        client.message(target, "{origin}: Couldn't find any quotes.".format(
            origin=origin
        ))

    quote = q[0]

    client.message(target, "{origin}: {quote}".format(
        origin=origin,
        quote=quote.as_text
    ))
