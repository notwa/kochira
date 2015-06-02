"""
Quote database.

This enables the bot to record and search quotes. If the web server service is
running, a web interface to quotes will be made available at ``/quotes/``.
"""

import random
import re
import operator
import itertools

from datetime import datetime
from peewee import CharField, TextField, DateTimeField, fn, SQL
from whoosh.analysis import StemmingAnalyzer
import whoosh.fields
import whoosh.index
import whoosh.query
import whoosh.writing
from whoosh.qparser import QueryParser

from kochira import config
from kochira.db import Model, database

from kochira.service import Service, Config, background
from kochira.auth import requires_permission

from tornado.web import RequestHandler, Application


service = Service(__name__, __doc__)

@service.config
class Config(Config):
    index_path = config.Field(doc="Path to the full-text index.", default="quotes")


stem_ana = StemmingAnalyzer()

WHOOSH_SCHEMA = whoosh.fields.Schema(
    id=whoosh.fields.NUMERIC(unique=True, stored=True),
    quote=whoosh.fields.TEXT(analyzer=stem_ana),
    by=whoosh.fields.ID(),
    ts=whoosh.fields.DATETIME(),
    channel=whoosh.fields.ID(),
    network=whoosh.fields.ID()
)


@service.model
class Quote(Model):
    by = CharField(255)
    quote = TextField()
    channel = CharField(255)
    network = CharField(255)
    ts = DateTimeField()

    class Meta:
        indexes = (
            (("channel", "network"), False),
        )


@service.setup
def initialize_model(ctx):
    if not whoosh.index.exists_in(ctx.config.index_path):
        ctx.storage.index = whoosh.index.create_in(ctx.config.index_path, WHOOSH_SCHEMA)
    else:
        ctx.storage.index = whoosh.index.open_dir(ctx.config.index_path)

    ctx.storage.quote_qp = QueryParser("quote", schema=WHOOSH_SCHEMA)
    ctx.storage.last_people_mappings = {}


def _add_quote(storage, network, channel, origin, quote):
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
def add_quote(ctx, quote):
    """
    Add quote.

    Add the given quote to the database.
    """

    quote = _add_quote(ctx.storage, ctx.client.network, ctx.target, ctx.origin, quote)

    ctx.respond(ctx._("Added quote {qid}.").format(
        qid=quote.id
    ))


def _delete_quote(storage, qid):
    with database.transaction():
        Quote.delete().where(Quote.id == qid).execute()
        storage.index.delete_by_term("id", qid)


@service.command(r"[iI](?: am|'m)(?: very| quite| extremely) butthurt about quote (?P<qid>\d+)$", mention=True)
@service.command(r"(?:destroy|remove|delete) quote (?P<qid>\d+)$", mention=True)
@service.command(r"!quote del (?P<qid>\d+)$")
@requires_permission("quote")
def delete_quote(ctx, qid: int):
    """
    Delete quote.

    Remove the given quote from the database.
    """

    if not Quote.select() \
        .where(Quote.id == qid,
               Quote.network == ctx.client.network,
               Quote.channel == ctx.target).exists():
        ctx.respond(ctx._("That's not a quote."))
        return

    _delete_quote(ctx.storage, qid)

    ctx.respond(ctx._("Deleted quote {qid}.").format(
        qid=qid
    ))


@service.command(r"what is quote (?P<qid>\d+)\??$", mention=True)
@service.command(r"read quote (?P<qid>\d+)$", mention=True)
@service.command(r"!quote read (?P<qid>\d+)$")
def read_quote(ctx, qid: int):
    """
    Read quote.

    Read a quote from the database.
    """

    q = Quote.select() \
        .where(Quote.id == qid)

    if not q.exists():
        ctx.respond(ctx._("That's not a quote."))
        return

    quote = q[0]

    ctx.respond(ctx._("Quote {id}: {text}").format(
        id=quote.id,
        text=quote.quote
    ))


@service.command(r"what is the last quote\??", mention=True)
@service.command(r"last quote", mention=True)
@service.command(r"!quote read last")
def last_quote(ctx):
    """
    Last quote.

    Get the last quote from the database.
    """

    q = Quote.select() \
        .order_by(Quote.id.desc()) \
        .limit(1)

    if not q.exists():
        ctx.respond(ctx._("There aren't any quotes."))
        return

    quote, = q

    ctx.respond(ctx._("Quote {id}: {text}").format(
        id=quote.id,
        text=quote.quote
    ))


@service.command(r"(?:give me a )?random quote(?: matching (?P<query>.+))?$", mention=True)
@service.command(r"!quote rand(?: (?P<query>.+))?$")
def rand_quote(ctx, query=None):
    """
    Random quote.

    Retrieve a random quote from the database. If a query is specified, then it is
    used.
    """

    if query is not None:
        q = _find_quotes(ctx.storage, query)
    else:
        q = Quote.select()

    q = q \
        .order_by(fn.Random()) \
        .limit(1)

    if not q.exists():
        ctx.respond(ctx._("Couldn't find any quotes."))
        return

    quote = q[0]

    ctx.respond(ctx._("Quote {id}: {text}").format(
        id=quote.id,
        text=quote.quote
    ))


NAMES = [
    "Sailor Venus",
    "Sailor Mercury",
    "Sailor Mars",
    "Sailor Jupiter",
    "Sailor Moon"
]

def prism_power(text, seed):
    people = []
    original_people = []

    for nick in re.findall(r"(?:^|[ \n])< ?[!~&@%+]?([A-Za-z0-9{}\[\]|^`\\_-]+)> ", text) + \
                re.findall(r"(?:^|[ \n])< ?[!~&@%+]?[A-Za-z0-9{}\[\]|^`\\_-]+>\s+([A-Za-z0-9{}\[\]|^`\\_-]+): ", text) + \
                re.findall(r"(?:^|[ \n])[!~&@%+]?([A-Za-z0-9{}\[\]|^`\\_-]+) \| ", text) + \
                re.findall(r"(?:^|[ \n])[!~&@%+]?[A-Za-z0-9{}\[\]|^`\\_-]+ \|\s+([A-Za-z0-9{}\[\]|^`\\_-]+): ", text) + \
                re.findall(r"(?:^|[ \n])\* ([A-Za-z0-9{}\[\]|^`\\_-]+)", text) + \
                re.findall(r"(?:^|[ \n])\*\*\* ([A-Za-z0-9{}\[\]|^`\\_-]+)", text) + \
                re.findall(r"(?:^|[ \n])-!- ([A-Za-z0-9{}\[\]|^`\\_-]+)", text):
        normalized_nick = nick.lower()
        if normalized_nick not in people:
            people.append(normalized_nick)
            original_people.append(nick)

    names = NAMES[:]
    random.Random(seed).shuffle(names)

    people_mappings = []

    for i, nick in enumerate(people):
        new_name = names[i % len(names)]
        people_mappings.append((original_people[i], new_name))

        text = re.sub(r"\b[!~&@%+]?" + re.escape(nick) + r"\b", new_name, text, 0, re.I)

    return text, people_mappings


@service.command(r"quote roulette(?: matching (?P<query>.+))?$", mention=True)
@service.command(r"!quote roulette(?: (?P<query>.+))?$")
def roulette(ctx, query=None):
    """
    Quote roulette.
    
    Retrieve a random quote from the database, anonymized. If a query is
    specified, then it is used.
    """

    if query is not None:
        q = _find_quotes(ctx.storage, query)
    else:
        q = Quote.select() \
            .where(Quote.network == ctx.client.network,
                   Quote.channel == ctx.target)

    q = q \
        .order_by(fn.Random()) \
        .limit(1)

    if not q.exists():
        ctx.respond(ctx._("Couldn't find any quotes."))
        return

    quote = q[0]
    text, people_mappings = prism_power(quote.quote, quote.quote)

    ctx.storage.last_people_mappings[ctx.client.network, ctx.target] = people_mappings
    ctx.respond(ctx._("Quote: {text}".format(text=text)))


@service.command(r"reveal quote$", mention=True)
@service.command(r"!quote reveal$")
def reveal(ctx):
    """
    Reveal.
    
    Reveal a rouletted quote.
    """
    last_mappings = ctx.storage.last_people_mappings.get((ctx.client.network, ctx.target))
    
    if last_mappings is None:
        ctx.respond(ctx._("Nobody has quote rouletted in this channel."))
        return

    ctx.respond(", ".join("{} = {}".format(orig, new) for new, orig in last_mappings))


def _find_quotes(storage, query):
    q = storage.quote_qp.parse(query)

    with storage.index.searcher() as searcher:
        results = searcher.search(q, limit=None)
        qids = [r["id"] for r in results]

    return Quote.select() \
        .where(Quote.id << SQL("({})".format(", ".join(str(qid) for qid in qids))))


@service.command(r"find (?:a )?quote matching (?P<query>.+)$", mention=True)
@service.command(r"!quote find (?P<query>.+)$")
def find_quote(ctx, query):
    """
    Find quote.

    Full-text search for a given quote.
    """
    quotes = list(_find_quotes(ctx.storage, query))

    if not quotes:
        ctx.respond(ctx._("Couldn't find any quotes."))
    elif len(quotes) == 1:
        ctx.respond(ctx._("Quote {id}: {text}").format(
            id=quotes[0].id,
            text=quotes[0].quote
        ))
    else:
        qids = [quote.id for quote in quotes]
        qids.sort()

        ctx.respond(ctx._("Found {num} quotes: {qids}").format(
            num=len(qids),
            qids=", ".join(str(qid) for qid in qids)
        ))


DIALOG_EXPR = re.compile(
    r"(?:<[ !~&@%+]?(?P<who>[A-Za-z0-9{}\[\]|^`\\_-]+)>) (?P<text>.*)")


@service.command(r"!quote comic(?: (?P<query>.+))?$")
@background
def comic_quote(ctx, query=None):
    """
    Comic quote.
    
    Make a quote into a comic.
    """
    try:
        make_comic = ctx.provider_for("make_comic")
    except KeyError:
        ctx.respond(ctx._("Sorry, I don't have a comic provider loaded."))
        return

    if query is not None:
        q = _find_quotes(ctx.storage, query)
    else:
        q = Quote.select()

    q = q \
        .order_by(fn.Random()) \
        .limit(1)

    if not q.exists():
        ctx.respond(ctx._("Couldn't find any quotes."))
        return

    dialogs = []
    stick_figures = []
    
    for line in guess_newlines(q[0].quote):
        match = DIALOG_EXPR.match(line)
        if match is None:
            continue
    
        speaker = match.group("who")
        if speaker not in stick_figures:
            stick_figures.append(speaker)
    
        text = match.group("text")
    
        dialogs.append({
            "speaker": speaker,
            "text": text
        })
    
    for dialog in dialogs:
        dialog["text"] = re.sub(
            r"^({names})[:,] ".format(names="|".join(
                re.escape(name) for name in stick_figures)),
            "", dialog["text"])
    
    clumps = [[]]
    
    for _, lines in itertools.groupby(dialogs, operator.itemgetter("speaker")):
        lines = list(lines)
    
        last_clump = clumps[-1]
    
        if not last_clump or len(last_clump) + len(lines) <= 3:
            last_clump.extend(lines)
        else:
            clumps.append(lines)
    
    panels = []
    for clump in clumps:
        while clump:
            cur, clump = clump[:3], clump[3:]
            panels.append({
                "stick_figures": stick_figures,
                "dialogs": cur
            })
    
    comic_spec = {
        "panels_per_row": 2,
        "panel_width": 600 + max([len(stick_figures) - 3, 0]) * 200,
        "panel_height": 600 + max([len(stick_figures) - 3, 0]) * 100,
        "title": "Kobun&!",
        "panels": panels
    }

    print(make_comic)
    try:
        comic = make_comic(comic_spec)
    except Exception as e:
        ctx.respond(ctx._("Couldn't generate a comic: {error}").format(error=e))
        raise
    else:
        ctx.respond(ctx._("Comic: {url}").format(url=comic))    


def guess_newlines(text):
    text = re.sub(
        r"(?:^| )(\[?(?:(?:(?:\d\d)?\d\d-\d\d-\d\d )?\d\d:\d\d(?::\d\d)?\]? )?" +
        r"(?:< ?[!~&@%+]?[A-Za-z0-9{}\[\]|^`\\_-]+> |[!~&@%+]?[A-Za-z0-9{}\[\]|^`\\_-]+ \| |\* |-!-|\*\*\*))", "\n\\1", text)
    text = re.sub(r"^\*", " *", text.strip(), re.M)
    return text.split("\n")


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

        query = self.get_argument("q", "")

        if query:
            q = _find_quotes(self.application.ctx.storage, query)
        else:
            q = Quote.select()

        q = q.order_by(Quote.id.desc())

        is_prism_power = self.get_argument("prism_power", "") == "activate"

        self.render("quotes/index.html",
                    query=query,
                    quotes=q.limit(limit).offset(offset),
                    count=q.count(),
                    limit=limit,
                    offset=offset,
                    get_quote_text=(lambda quote: prism_power("\n".join(guess_newlines(quote.quote)), quote.quote)[0].split("\n"))
                                   if is_prism_power else
                                   (lambda quote: guess_newlines(quote.quote)),
                    prism_power=is_prism_power)


def make_application(settings):
    return Application([
        (r"/", IndexHandler)
    ], **settings)


@service.hook("services.net.webserver")
def webserver_config(ctx):
    return {
        "name": "quotes",
        "title": "Quotes",
        "application_factory": make_application
    }

