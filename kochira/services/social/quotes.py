"""
Quote database.

This enables the bot to record and search quotes. If the web server service is
running, a web interface to quotes will be made available at ``/quotes/``.

Configuration Options
=====================

``index_path``
  Path to use for the full-text index.

Commands
========

Add Quote
---------

::

    $bot: add quote <quote>
    !quote add <quote>

**Requires permission:** quote

Add the given quote to the database.

Delete Quote
------------

::

    $bot: delete quote <qid>
    !quote del <qid>
    $bot: i am very butthurt about quote <qid>

**Requires permission:** quote

Remove the given quote from the database.

Read Quote
----------

::

    $bot: what is quote <qid>
    $bot: read quote <qid>
    !quote read <qid>

Read a quote from the database.

Random Quote
------------

::

    $bot: random quote
    !quote rand

Retrieve a random quote from the database.

Find Quote
----------

::

    $bot: find a quote matching <query>
    !quote find <query>

Full-text search for a given quote.
"""

import re

from datetime import datetime
from peewee import CharField, TextField, DateTimeField, fn, SQL
from whoosh.analysis import StemmingAnalyzer
import whoosh.fields
import whoosh.index
import whoosh.query
import whoosh.writing
from whoosh.qparser import QueryParser

from kochira.db import Model, database

from kochira.service import Service
from kochira.auth import requires_permission

from tornado.web import RequestHandler, Application, HTTPError


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

    @property
    def quote_with_newlines(self):
        text = self.quote
        text = re.sub(r"(?:^| )(\[?(?:(?:(?:\d\d)?\d\d-\d\d-\d\d )?\d\d:\d\d(?::\d\d)?\]? )?(?:< ?[!~&@%+]?[A-Za-z0-9{}\[\]|^`\\_-]+>|\* |-!-))", "\n\\1", text)
        text = re.sub(r"^\*", " *", text, re.M)
        return text

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


def _add_quote(bot, network, channel, origin, quote):
    storage = service.storage_for(bot)

    with database.transaction():
        quote = Quote.create(by=origin, quote=quote, channel=channel,
                             network=network, ts=datetime.utcnow())
        quote.save()

        with storage.index.writer() as writer:
            writer.add_document(id=quote.id, by=quote.by,
                                quote=quote.quote, channel=quote.channel,
                                network=quote.network, ts=quote.ts)

    return quote


@service.command(r"add quote (?P<quote>.+)$", mention=True)
@service.command(r"!quote add (?P<quote>.+)$")
@requires_permission("quote")
def add_quote(client, target, origin, quote):
    quote = _add_quote(client.bot, client.network, target, origin, quote)

    client.message(target, "{origin}: Added quote {qid}.".format(
        origin=origin,
        qid=quote.id
    ))


def _delete_quote(bot, qid):
    storage = service.storage_for(bot)

    with database.transaction():
        Quote.delete().where(Quote.id == qid).execute()
        storage.index.delete_by_term("id", qid)


@service.command(r"[iI](?: am|'m)(?: very| quite| extremely) butthurt about quote (?P<qid>\d+)$", mention=True)
@service.command(r"(?:destroy|remove|delete) quote (?P<qid>\d+)$", mention=True)
@service.command(r"!quote del (?P<qid>\d+)$")
@requires_permission("quote")
def delete_quote(client, target, origin, qid: int):
    if not Quote.select() \
        .where(Quote.id == qid,
               Quote.network == client.network,
               Quote.channel == target).exists():
        client.message(target, "{origin}: That's not a quote.".format(
            origin=origin
        ))
        return

    _delete_quote(client.bot, qid)

    client.message(target, "{origin}: Deleted quote {qid}.".format(
        origin=origin,
        qid=qid
    ))


def _read_quote(bot, qid):
    try:
        return Quote.get(Quote.id == qid)
    except Quote.DoesNotExist:
        return None


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


def _rand_quote(bot, network, channel):
    q = Quote.select() \
        .where(Quote.network == network, Quote.channel == channel) \
        .order_by(fn.Random()) \
        .limit(1)

    if not q.exists():
        return None

    return q[0]


@service.command(r"(?:give me a )?random quote$", mention=True)
@service.command(r"!quote rand$")
def rand_quote(client, target, origin):
    quote = _rand_quote(client.bot, client.network, target)

    if quote is None:
        client.message(target, "{origin}: Couldn't find any quotes.".format(
            origin=origin
        ))
        return

    client.message(target, "{origin}: {quote}".format(
        origin=origin,
        quote=quote.as_text
    ))


def _find_quotes(bot, query):
    storage = service.storage_for(bot)

    q = storage.quote_qp.parse(query)

    with storage.index.searcher() as searcher:
        results = searcher.search(q, limit=None)
        qids = [r["id"] for r in results]

    return Quote.select() \
        .where(Quote.id << SQL("({})".format(", ".join(str(qid) for qid in qids))))


@service.command(r"find (?:a )?quote matching (?P<query>.+)$", mention=True)
@service.command(r"!quote find (?P<query>.+)$")
def find_quote(client, target, origin, query):
    quotes = list(_find_quotes(client.bot, query).where(
        Quote.network == client.network,
        Quote.channel == target
    ))

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
        qids = [quote.id for quote in quotes]
        qids.sort()

        client.message(target, "{origin}: Found {num} quotes: {qids}".format(
            origin=origin,
            num=len(qids),
            qids=", ".join(str(qid) for qid in qids)
        ))


class IndexHandler(RequestHandler):
    def get(self):
        try:
            limit = int(self.get_argument("limit", 20))
        except ValueError:
            limit = 20

        try:
            offset = int(self.get_argument("offset", 0))
        except ValueError:
            offset = 0

        query = self.get_argument("q", None)

        if query is not None:
            q = _find_quotes(self.application.bot, query)
        else:
            q = Quote.select()

        q = q.order_by(Quote.id.desc())

        self.render("quotes/index.html",
                    query=query,
                    quotes=q.limit(limit).offset(offset),
                    count=q.count(),
                    limit=limit,
                    offset=offset)


def make_application(settings):
    return Application([
        (r"/", IndexHandler)
    ], **settings)


@service.hook("services.net.webserver")
def webserver_config(bot):
    return {
        "name": "quotes",
        "title": "Quotes",
        "application_factory": make_application
    }

