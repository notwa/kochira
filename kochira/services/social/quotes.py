from datetime import datetime
from peewee import CharField, TextField, DateTimeField, fn
from whoosh.analysis import StemmingAnalyzer
import whoosh.fields
import whoosh.index
import whoosh.query
import whoosh.writing
from whoosh.qparser import QueryParser

from kochira.db import Model, database

from kochira.service import Service
from kochira.auth import requires_permission

service = Service(__name__, __doc__)

stem_ana = StemmingAnalyzer()

WHOOSH_SCHEMA = whoosh.fields.Schema(
    id=whoosh.fields.NUMERIC(unique=True, stored=True),
    quote=whoosh.fields.TEXT(analyzer=stem_ana),
    by=whoosh.fields.ID(),
    ts=whoosh.fields.DATETIME(),
    channel=whoosh.fields.ID(),
    network=whoosh.fields.ID()
)


class Quote(Model):
    by = CharField(255)
    quote = TextField()
    channel = CharField(255)
    network = CharField(255)
    ts = DateTimeField()

    @property
    def as_text(self):
        return "Quote {id}: {quote}".format(
            id=self.id,
            quote=self.quote
        )

    class Meta:
        indexes = (
            (("channel", "network"), False),
        )


@service.setup
def initialize_model(bot):
    config = service.config_for(bot)
    storage = service.storage_for(bot)

    if not whoosh.index.exists_in(config["index_path"]):
        storage.index = whoosh.index.create_in(config["index_path"], WHOOSH_SCHEMA)
    else:
        storage.index = whoosh.index.open_dir(config["index_path"])

    storage.quote_qp = QueryParser("quote", schema=WHOOSH_SCHEMA)
    Quote.create_table(True)


@service.command(r"add quote (?P<quote>.+)$", mention=True)
@service.command(r"!quote add (?P<quote>.+)$")
@requires_permission("quote")
def add_quote(client, target, origin, quote):
    storage = service.storage_for(client.bot)

    with database.transaction():
        quote = Quote.create(by=origin, quote=quote, channel=target,
                             network=client.network, ts=datetime.utcnow())
        quote.save()

        with storage.index.writer() as writer:
            writer.add_document(id=quote.id, by=quote.by,
                                quote=quote.quote, channel=quote.channel,
                                network=quote.network, ts=quote.ts)

    client.message(target, "{origin}: Added quote {qid}.".format(
        origin=origin,
        qid=quote.id
    ))


@service.command(r"[iI](?: am|'m)(?: very| quite| extremely) butthurt about quote (?P<qid>\d+)$", mention=True)
@service.command(r"(?:destroy|remove|delete) quote (?P<qid>\d+)$", mention=True)
@service.command(r"!quote del (?P<qid>\d+)$")
@requires_permission("quote")
def delete_quote(client, target, origin, qid: int):
    storage = service.storage_for(client.bot)

    if not Quote.select() \
        .where(Quote.id == qid,
               Quote.network == client.network,
               Quote.channel == target).exists():
        client.message(target, "{origin}: That's not a quote.".format(
            origin=origin
        ))
        return

    with database.transaction():
        Quote.delete().where(Quote.id == qid).execute()
        storage.index.delete_by_term("id", qid)

    client.message(target, "{origin}: Deleted quote {qid}.".format(
        origin=origin,
        qid=qid
    ))


@service.command(r"what is quote (?P<qid>\d+)\??$", mention=True)
@service.command(r"read quote (?P<qid>\d+)$", mention=True)
@service.command(r"!quote read (?P<qid>\d+)$")
def read_quote(client, target, origin, qid: int):
    q = Quote.select() \
        .where(Quote.id == qid,
               Quote.network == client.network,
               Quote.channel == target)

    if not q.exists():
        client.message(target, "{origin}: That's not a quote.".format(
            origin=origin
        ))
        return

    quote = q[0]

    client.message(target, "{origin}: {quote}".format(
        origin=origin,
        quote=quote.as_text
    ))


@service.command(r"(?:give me a )?random quote$", mention=True)
@service.command(r"!quote rand$")
def rand_quote(client, target, origin):
    q = Quote.select() \
        .where(Quote.network == client.network, Quote.channel == target) \
        .order_by(fn.Random()) \
        .limit(1)

    if not q.exists():
        client.message(target, "{origin}: Couldn't find any quotes.".format(
            origin=origin
        ))
        return

    quote = q[0]

    client.message(target, "{origin}: {quote}".format(
        origin=origin,
        quote=quote.as_text
    ))


@service.command(r"find (?:a )?quote matching (?P<query>.+)$", mention=True)
@service.command(r"!quote find (?P<query>.+)$")
def find_quote(client, target, origin, query):
    storage = service.storage_for(client.bot)

    q = storage.quote_qp.parse(query)

    with storage.index.searcher() as searcher:
        results = searcher.search(q, limit=None)
        qids = [r["id"] for r in results]

    quotes = list(Quote.select()
        .where(Quote.network == client.network,
               Quote.channel == target,
               Quote.id << qids))

    if not quotes:
        client.message(target, "{origin}: Couldn't find any quotes.".format(
            origin=origin
        ))
    elif len(quotes) == 1:
        client.message(target, "{origin}: {quote}".format(
            origin=origin,
            quote=quotes[0].as_text
        ))
    else:
        client.message(target, "{origin}: Found {num} quotes: {qids}".format(
            origin=origin,
            num=len(qids),
            qids=", ".join(str(qid) for qid in sorted(qids))
        ))
