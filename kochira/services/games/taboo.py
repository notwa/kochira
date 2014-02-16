"""
Taboo game.

Players take turns describing a word or phrase on a drawn card to their partner
without using five common additional words.
"""

from collections import OrderedDict

from kochira.auth import requires_permission
from kochira.service import Service, requires_context
from kochira.db import Model

import peewee

service = Service(__name__, __doc__)


@service.setup
def setup_contexts(bot):
    storage = service.storage_for(bot)
    storage.games = {}


@service.model
class Taboo(Model):
    title = peewee.CharField(255)
    taboo1 = peewee.CharField(255)
    taboo2 = peewee.CharField(255)
    taboo3 = peewee.CharField(255)
    taboo4 = peewee.CharField(255)
    taboo5 = peewee.CharField(255)

    @property
    def taboos(self):
        return {self.title, self.taboo1, self.taboo2, self.taboo3, self.taboo4, self.taboo5}

    class Meta:
        indexes = (
            (("title",), True),
        )


class TabooStateError(Exception):
    def __init__(self, code):
        self.code = code

    NO_MORE_CARDS = 0


class Game:
    TURN_DURATION = 30

    def __init__(self):
        q = Taboo.select().order_by(peewee.fn.Random())

        if not q.exists():
            raise TabooStateError(TabooStateError.NO_MORE_CARDS)

        self.cards = iter(q)
        self.started = False

        self.players = []
        self.teams = [0, 0]

        self._turn_index = 0

    def draw(self):
        try:
            self.card = next(self.cards)
        except StopIteration:
            raise TabooStateError(TabooStateError.NO_MORE_CARDS)

    @property
    def team(self):
        return self._turn_index % 2

    @property
    def turn(self):
        return self.players[self._turn_index]

    @property
    def guessers(self):
        return [p for p in self.players[self.team::2]
                if p != self.turn]

    def _next_turn_index(self):
        return (self._turn_index + 1) % len(self.players)

    def advance(self):
        self._turn_index = self._next_turn_index()

    def submit_clue(self, sentence):
        for taboo in self.card.taboos:
            if taboo in sentence:
                return taboo
        return None

    def submit_guess(self, sentence):
        if self.card.title in sentence:
            self.teams[self.team] += 1
            return True
        return False

    def join(self, player):
        if player in self.players:
            raise ValueError("player is already playing")

        self.players.append(player)

    def leave(self, player):
        self.players.remove(player)
        if self.players:
            self._turn_index %= len(self.players)
        return not self.players or (self.started and len(self.players) < 4)

    def start(self):
        if len(self.players) < 4:
            raise ValueError("not enough players")
        self.started = True

    def stop(self):
        self.started = False


@service.command(r"!taboo add (?P<title>[^:]+): (?P<taboo1>[^,]+), (?P<taboo2>[^,]+), (?P<taboo3>[^,]+), (?P<taboo4>[^,]+), (?P<taboo5>[^,]+)")
@service.command(r"add taboo (?P<title>[^:]+): (?P<taboo1>[^,]+), (?P<taboo2>[^,]+), (?P<taboo3>[^,]+), (?P<taboo4>[^,]+), (?P<taboo5>[^,]+)", mention=True)
@requires_permission("taboo")
def add_taboo(client, target, origin, title, taboo1, taboo2, taboo3, taboo4, taboo5):
    """
    Add a Taboo card.

    (It has five parameters because the regex can strictly validate the
    command. YES, I KNOW WHAT ``str.split`` IS.)
    """
    if Taboo.select().where(Taboo.title == title).exists():
        client.message(target, "{origin}: That Taboo card already exists.".format(
            origin=origin
        ))
        return

    taboo = Taboo.create(title=title.strip().lower(),
                         taboo1=taboo1.strip().lower(),
                         taboo2=taboo2.strip().lower(),
                         taboo3=taboo3.strip().lower(),
                         taboo4=taboo4.strip().lower(),
                         taboo5=taboo5.strip().lower())

    taboo.save()
    client.message(target, "{origin}: Added Taboo card \"{title}\", with taboos: {taboos}.".format(
        origin=origin,
        title=taboo.title,
        taboos=", ".join(taboo.taboos)
    ))


@service.command(r"!taboo del (?P<title>.+)")
@service.command(r"(?:remove|delete) taboo card (?P<title>.+)", mention=True)
@requires_permission("taboo")
def remove_taboo(client, target, origin, title):
    """
    Remove a Taboo card.

    Delete a Taboo card from the database.
    """
    title = title.lower()

    if Taboo.delete().where(Taboo.title == title).execute() == 0:
        client.message(target, "{origin}: Can't find that Taboo card.".format(
            origin=origin
        ))
    else:
        client.message(target, "{origin}: Deleted Taboo card \"{title}\".".format(
            origin=origin,
            title=title
        ))


@service.command(r"!taboo")
@service.command(r"taboo", mention=True)
def request_taboo(client, target, origin):
    """
    Request a game of Taboo.

    Initiate a game of Taboo.
    """
    storage = service.storage_for(client.bot)

    k = (client.name, target)

    if k in storage.games:
        client.message(target, "{origin}: A game is already in progress.".format(
            origin=origin
        ))
        return

    try:
        g = Game()
    except TabooStateError as e:
        if e.code != TabooStateError.NO_MORE_CARDS:
            raise

        client.message(target, "{origin}: There are no Taboo cards.".format(
            origin=origin
        ))
        return

    g.period = None
    g.join(origin)
    storage.games[k] = g

    client.message(target, "{origin} has started a game of Taboo! Send !join to join, and !start when ready!".format(
        origin=origin
    ))

    service.add_context(client, "taboo", target)


@service.command(r"!join")
@requires_context("taboo")
def join_taboo(client, target, origin):
    """
    Join game.

    Join a Taboo game in progress.
    """
    storage = service.storage_for(client.bot)
    game = storage.games[client.name, target]

    if origin in game.players:
        client.message(target, "{origin}: You're already in the game.".format(
            origin=origin
        ))
        return

    game.join(origin)

    client.message(target, "{origin} has joined the game!".format(
        origin=origin
    ))


@service.command(r"!leave")
@requires_context("taboo")
def leave(client, target, origin):
    """
    Leave game.

    Leave the game, if you're participating.
    """
    storage = service.storage_for(client.bot)
    game = storage.games[client.name, target]

    if origin not in game.players:
        client.message(target, "{origin}: You're not in this game.".format(
            origin=origin
        ))
        return

    game_over = game.leave(origin)

    if game_over:
        do_game_over(client, target)
        return

    client.message(target, "{origin} left the game.".format(
        origin=origin
    ))

    if game.started:
        send_summary(client, target)


def show_scores(game):
    team1 = ", ".join(list(game.players)[::2])
    team2 = ", ".join(list(game.players)[1::2])

    scores = [(team1, game.teams[0]), (team2, game.teams[1])]
    scores.sort(key=lambda x: x[1])

    return "; ".join("{}: {}".format(k, v) for k, v in scores)


def send_summary(client, target):
    storage = service.storage_for(client.bot)
    game = storage.games[client.name, target]

    client.message(target, "{turn}: It's your turn -- explain your word but don't say any of the taboos! {guessers} {isare} guessing. You have {time} seconds.".format(
        turn=game.turn,
        guessers=", ".join(game.guessers),
        time=Game.TURN_DURATION,
        isare="is" if len(game.guessers) == 1 else "are"
    ))


def do_game_over(client, target, prefix=""):
    storage = service.storage_for(client.bot)

    game = storage.games[client.name, target]
    game.stop()

    if game.period is not None:
        client.bot.scheduler.unschedule_period(game.period)

    client.message(target, prefix + "Game over! Final results: {results}".format(
        results=show_scores(game)
    ))
    del storage.games[client.name, target]
    service.remove_context(client, "taboo", target)


@service.command(r"!stop")
@requires_context("taboo")
def stop_taboo(client, target, origin):
    """
    Stop Taboo.

    Stop the Taboo game in progress.
    """
    do_game_over(client, target)


@service.command(r"!start")
@requires_context("taboo")
def start_taboo(client, target, origin):
    """
    Start Taboo.

    Start the Taboo game.
    """
    storage = service.storage_for(client.bot)
    game = storage.games[client.name, target]

    if origin not in game.players:
        client.message(target, "{origin}: You're not in this game.".format(
            origin=origin
        ))
        return

    if game.started:
        client.message(target, "{origin}: This game is already in progress.".format(
            origin=origin
        ))
        return

    if len(game.players) < 4:
        client.message(target, "{origin}: There aren't enough players to play yet.".format(
            origin=origin
        ))
        return

    game.start()

    send_summary(client, target)
    do_draw(client, target)

    game.period = client.bot.scheduler.schedule_every(Game.TURN_DURATION, do_advance, client, target, game)


@service.task
def do_advance(bot, client, target, game):
    client.message(target, "{turn}: Time is up!".format(
        turn=game.turn
    ))

    if do_draw(client, target):
        return

    game.advance()
    send_summary(client, target)


def do_draw(client, target):
    storage = service.storage_for(client.bot)
    game = storage.games[client.name, target]

    try:
        game.draw()
    except TabooStateError as e:
        if e.code != TabooStateError.NO_MORE_CARDS:
            raise
        do_game_over(client, target, "Looks like we ran out of cards! ")
        return True

    client.notice(game.turn, "Title: {title}; Taboos: {taboos}".format(
        title=game.card.title,
        taboos=", ".join(game.card.taboos)
    ))
    return False


@service.hook("channel_message")
def do_guess(client, target, origin, message):
    if not service.has_context(client, "taboo", target):
        # nobody is playing taboo.
        return

    storage = service.storage_for(client.bot)

    game = storage.games[client.name, target]

    if not game.started:
        # taboo hasn't started yet.
        return

    card = game.card

    if origin == game.turn:
        maybe_taboo = game.submit_clue(message)
        if maybe_taboo is not None:
            client.message(target, "{origin}: BZZT! You said \"{taboo}\". The word was \"{title}\".".format(
                origin=origin,
                taboo=maybe_taboo,
                title=card.title
            ))
            do_draw(client, target)
    elif origin in game.guessers:
        if game.submit_guess(message):
            client.message(target, "{origin}: Ding-ding! The word was \"{title}\". 1 point for team {n}.".format(
                origin=origin,
                title=card.title,
                n=game.team + 1
            ))
            do_draw(client, target)
