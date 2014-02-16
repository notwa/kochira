"""
Uno card game.

The popular card game Uno, now on IRC.
"""

import random
import itertools
from collections import OrderedDict

from kochira.service import Service, requires_context

service = Service(__name__, __doc__)


@service.setup
def setup_contexts(bot):
    storage = service.storage_for(bot)
    storage.games = {}


class UnoStateError(Exception):
    def __init__(self, code):
        self.code = code

    HAS_ALREADY_DRAWN = 0
    MUST_DRAW_FIRST = 1
    NOT_IN_HAND = 2
    CARD_NOT_COMPATIBLE = 3
    NO_MORE_DRAWS = 4


class Game:
    RED = "r"
    GREEN = "g"
    BLUE = "b"
    YELLOW = "y"
    WILD = "w"

    DRAW_TWO = 10
    REVERSE = 11
    SKIP = 12
    DRAW_FOUR = 13
    WILD_RANK = 14

    SPECIAL_RANKS = {10, 11, 12, 13}

    def __init__(self, pile=None):
        self.draw_pile = list(pile or Game.SETS["standard"])
        random.shuffle(self.draw_pile)

        self.started = False
        self.players = OrderedDict()

    def _draw(self):
        if not self.draw_pile:
            raise UnoStateError(UnoStateError.NO_MORE_DRAWS)
        return self.draw_pile.pop()

    def _next_turn_index(self):
        return (self._turn_index + self.direction) % len(self.players)

    def _advance(self):
        self._turn_index = self._next_turn_index()

    @staticmethod
    def show_card(card):
        color, rank = card
        return {
            Game.RED: "r",
            Game.GREEN: "g",
            Game.BLUE: "b",
            Game.YELLOW: "y",
            Game.WILD: "w"
        }[color] + {
            Game.DRAW_TWO: "D2",
            Game.REVERSE: "R",
            Game.SKIP: "S",
            Game.DRAW_FOUR: "D4",
            Game.WILD_RANK: "W"
        }.get(rank, str(rank))

    @staticmethod
    def read_card(s):
        raw_color, *raw_rank = s
        raw_rank = "".join(raw_rank).upper()

        color = {
            "r": Game.RED,
            "g": Game.GREEN,
            "b": Game.BLUE,
            "y": Game.YELLOW,
            "w": Game.WILD
        }[raw_color.lower()]

        try:
            rank = int(raw_rank)
        except ValueError:
            try:
                rank = {
                    "D2": Game.DRAW_TWO,
                    "R": Game.REVERSE,
                    "S": Game.SKIP,
                    "D4": Game.DRAW_FOUR,
                    "W": Game.WILD_RANK
                }[raw_rank]
            except KeyError:
                raise ValueError("illegal rank")
        else:
            if not (0 <= rank <= 9):
                raise ValueError("illegal numerical rank")

        return (color, rank)

    def turn_draw(self):
        if self.has_drawn:
            raise UnoStateError(UnoStateError.HAS_ALREADY_DRAWN)

        card = self._draw()
        self.players[self.turn].append(card)
        self.has_drawn = True
        return card

    def turn_pass(self):
        if not self.has_drawn and self.must_draw == 0:
            raise UnoStateError(UnoStateError.MUST_DRAW_FIRST)

        self.players[self.turn].extend([self._draw() for _ in range(self.must_draw)])

        self._advance()
        self.must_draw = 0

    def join(self, player):
        hand = []

        for _ in range(7):
            hand.append(self._draw())

        self.players[player] = hand

    def leave(self, player):
        hand = self.players[player]
        del self.players[player]
        self.draw_pile.extend(hand)
        random.shuffle(self.draw_pile)

        self._turn_index %= len(self.players)

        return not self.players or (self.started and len(self.players) <= 1)

    def play(self, card, target_color=None):
        color, rank = card
        top_color, top_rank = self.top

        if card not in self.players[self.turn]:
            raise UnoStateError(UnoStateError.NOT_IN_HAND)

        if self.must_draw > 0 and rank not in Game.SPECIAL_RANKS:
            raise UnoStateError(UnoStateError.CARD_NOT_COMPATIBLE)

        if color == Game.WILD:
            if target_color not in (Game.RED, Game.GREEN, Game.BLUE, Game.YELLOW):
                raise ValueError("must specify a valid target color")
            self.players[self.turn].remove(card)
            self.top = (target_color, rank)
        elif top_color == color or top_color == Game.WILD:
            self.players[self.turn].remove(card)
            self.top = card
        elif top_rank == rank:
            self.players[self.turn].remove(card)
            self.top = card
        else:
            raise UnoStateError(UnoStateError.CARD_NOT_COMPATIBLE)

        self.has_drawn = False

        if not self.players[self.turn]:
            return True

        # now handle special cards
        if rank == Game.DRAW_TWO:
            self.must_draw += 2
        elif rank == Game.SKIP:
            self._advance()
        elif rank == Game.REVERSE:
            self.direction = -self.direction
        elif rank == Game.DRAW_FOUR:
            self.must_draw += 4

        self._advance()

        return False

    @property
    def turn(self):
        return list(self.players.keys())[self._turn_index]

    @property
    def next_turn(self):
        return list(self.players.keys())[self._next_turn_index()]

    def start(self):
        if len(self.players) < 2:
            raise ValueError("need at least two players")

        self.started = True
        self.turns = list(self.players.keys())
        self._turn_index = 0
        self.direction = 1
        self.must_draw = 0

        self.top = self._draw()

    def scores(self):
        return sorted(self.players.items(), key=lambda x: len(x[1]))


Game.SETS = {
    "standard":
        [(color, 0) for color in [Game.RED, Game.GREEN, Game.BLUE, Game.YELLOW]] +
        [card for card in itertools.product([Game.RED, Game.GREEN, Game.BLUE, Game.YELLOW], range(1, 10))] * 2 +
        [(color, Game.DRAW_TWO) for color in [Game.RED, Game.GREEN, Game.BLUE, Game.YELLOW]] * 2 +
        [(color, Game.REVERSE) for color in [Game.RED, Game.GREEN, Game.BLUE, Game.YELLOW]] * 2 +
        [(color, Game.SKIP) for color in [Game.RED, Game.GREEN, Game.BLUE, Game.YELLOW]] * 2 +
        [(Game.WILD, Game.WILD_RANK)] * 4 +
        [(Game.WILD, Game.DRAW_FOUR)] * 4,
    "hitler":
        [(color, Game.DRAW_TWO) for color in [Game.RED, Game.GREEN, Game.BLUE, Game.YELLOW]] * 4 +
        [(color, Game.REVERSE) for color in [Game.RED, Game.GREEN, Game.BLUE, Game.YELLOW]] * 8 +
        [(color, Game.SKIP) for color in [Game.RED, Game.GREEN, Game.BLUE, Game.YELLOW]] * 8 +
        [(Game.WILD, Game.DRAW_FOUR)] * 8,
    "bland":
        [(color, 0) for color in [Game.RED, Game.GREEN, Game.BLUE, Game.YELLOW]] +
        [card for card in itertools.product([Game.RED, Game.GREEN, Game.BLUE, Game.YELLOW], range(1, 10))] * 2
}


def show_card_irc(card):
    color, rank = card
    return "\x03" + {
        Game.RED: "04r",
        Game.GREEN: "03g",
        Game.BLUE: "02b",
        Game.YELLOW: "07y",
        Game.WILD: "00,01w"
    }[color] + {
        Game.DRAW_TWO: "D2",
        Game.REVERSE: "R",
        Game.SKIP: "S",
        Game.DRAW_FOUR: "D4",
        Game.WILD_RANK: "W"
    }.get(rank, str(rank)) + "\x03"


def show_scores(game):
    return ", ".join("{} ({} cards)".format(k, len(v))
                     for k, v in game.scores())

def send_summary(client, target, game, prefix=""):
    client.message(target, "{turn}: {prefix}It's your turn.{stack} Top card ({count} left): {top}".format(
        turn=game.turn,
        prefix=prefix,
        count=len(game.draw_pile),
        stack=" Stack a special card or pass and draw {}.".format(game.must_draw) if game.must_draw > 0 else "",
        top=show_card_irc(game.top)
    ))


def send_hand(client, player, game):
    client.notice(player, "Your hand: {hand}".format(
        hand=" ".join(show_card_irc(card) for card in game.players[player])
    ))


def do_game_over(client, target, prefix=""):
    storage = service.storage_for(client.bot)

    game = storage.games[client.name, target]

    client.message(target, prefix + "Game over! Final results: {results}".format(
        results=show_scores(game)
    ))
    del storage.games[client.name, target]
    service.remove_context(client, "uno", target)


@service.command(r"uno(?: (?P<set>.+))?", mention=True)
@service.command(r"!uno(?: (?P<set>.+))?")
def start_uno(client, target, origin, set=None):
    """
    Start game.

    Start a game of Uno.
    """
    storage = service.storage_for(client.bot)

    k = (client.name, target)

    if k in storage.games:
        client.message(target, "{origin}: A game is already in progress.".format(
            origin=origin
        ))
        return

    if set is not None:
        try:
            set = Game.SETS[set.lower()]
        except:
            client.message(target, "{origin}: I don't know what set \"{set}\" is.".format(
                origin=origin,
                set=set
            ))
            return

    g = Game(set)
    g.join(origin)
    storage.games[k] = g

    client.message(target, "{origin} has started a game of Uno! Send !join to join, and !deal to deal when ready!".format(
        origin=origin
    ))

    service.add_context(client, "uno", target)


@service.command(r"!stop")
@requires_context("uno")
def stop_uno(client, target, origin):
    """
    Stop game.

    Stop the Uno game in progress.
    """
    storage = service.storage_for(client.bot)
    del storage.games[client.name, target]
    service.remove_context(client, "uno", target)
    client.message(target, "{origin} has stopped the game.".format(
        origin=origin
    ))


@service.command(r"!join")
@requires_context("uno")
def join_uno(client, target, origin):
    """
    Join game.

    Join an Uno game in progress.
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


@service.command(r"!deal")
@requires_context("uno")
def deal_uno(client, target, origin):
    """
    Deal for game.

    Deal cards to players in game.
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

    if len(game.players) < 2:
        client.message(target, "{origin}: There aren't enough players to deal yet.".format(
            origin=origin
        ))
        return

    client.message(target, "The game has started! Players: {players}".format(
        players=", ".join(game.players.keys())
    ))
    game.start()

    send_summary(client, target, game)
    for player in game.players.keys():
        send_hand(client, player, game)


@service.command(r"!play (?P<raw_card>\S+)(?: (?P<target_color>.))?")
@requires_context("uno")
def play_card(client, target, origin, raw_card, target_color=None):
    """
    Play card.

    Play an Uno card for the in-progress game.
    """
    storage = service.storage_for(client.bot)
    game = storage.games[client.name, target]

    if origin not in game.players:
        client.message(target, "{origin}: You're not in this game.".format(
            origin=origin
        ))
        return

    if origin != game.turn:
        client.message(target, "{origin}: It's not your turn.".format(
            origin=origin
        ))
        return

    try:
        card = Game.read_card(raw_card)
    except ValueError:
        client.message(target, "{origin}: I don't know what card that is.".format(
            origin=origin
        ))
        return

    color, rank = card

    if target_color is not None and color != Game.WILD:
        client.message(target, "{origin}: This isn't a wild card, dumbass.".format(
            origin=origin
        ))
        return

    if target_color is None and color == Game.WILD:
        client.message(target, "{origin}: You need to give me a color to change to, e.g.: !play wd4 r".format(
            origin=origin
        ))
        return

    last_turn = game.turn
    usual_turn = game.next_turn

    try:
        game_over = game.play(card, {
            "r": Game.RED,
            "g": Game.GREEN,
            "b": Game.BLUE,
            "y": Game.YELLOW
        }.get(target_color))
    except UnoStateError as e:
        if e.code == UnoStateError.CARD_NOT_COMPATIBLE:
            client.message(target, "{origin}: You can't play that card right now.".format(
                origin=origin
            ))
            return
        elif e.code == UnoStateError.NOT_IN_HAND:
            client.message(target, "{origin}: You don't have that card.".format(
                origin=origin
            ))
            return
    except ValueError:
        client.message(target, "{origin}: That's not a valid target color.".format(
            origin=origin
        ))
        return

    if game_over:
        do_game_over(client, target)
        return

    if len(game.players[last_turn]) == 1:
        client.message(target, "{player} has UNO!".format(
            player=last_turn
        ))

    prefix = ""

    if rank == Game.REVERSE:
        prefix = "Order reversed! "
    elif rank == Game.DRAW_TWO:
        prefix = "Draw two! "
    elif rank == Game.DRAW_FOUR:
        prefix = "Draw four! "
    elif rank == Game.SKIP:
        prefix = "{} was skipped! ".format(usual_turn)

    send_summary(client, target, game, prefix)
    send_hand(client, game.turn, game)


@service.command(r"!draw")
@requires_context("uno")
def draw(client, target, origin):
    """
    Draw.

    Draw a card from the pile.
    """
    storage = service.storage_for(client.bot)
    game = storage.games[client.name, target]

    if origin not in game.players:
        client.message(target, "{origin}: You're not in this game.".format(
            origin=origin
        ))
        return

    if origin != game.turn:
        client.message(target, "{origin}: It's not your turn.".format(
            origin=origin
        ))
        return

    try:
        card = game.turn_draw()
    except UnoStateError as e:
        if e.code == UnoStateError.HAS_ALREADY_DRAWN:
            client.message(target, "{origin}: You've already drawn.".format(
                origin=origin
            ))
            return
        elif e.code == UnoStateError.NO_MORE_DRAWS:
            do_game_over(client, target, "Looks like the pile ran out! ")
            return
        raise

    client.notice(origin, "You drew: {}".format(show_card_irc(card)))
    client.message(target, "{origin} draws.".format(origin=origin))


@service.command(r"!pass")
@requires_context("uno")
def pass_(client, target, origin):
    """
    Pass.

    Pass, if a card has been drawn.
    """
    storage = service.storage_for(client.bot)
    game = storage.games[client.name, target]

    if origin not in game.players:
        client.message(target, "{origin}: You're not in this game.".format(
            origin=origin
        ))
        return

    if origin != game.turn:
        client.message(target, "{origin}: It's not your turn.".format(
            origin=origin
        ))
        return

    must_draw = game.must_draw

    try:
        card = game.turn_pass()
    except UnoStateError as e:
        if e.code == UnoStateError.MUST_DRAW_FIRST:
            client.message(target, "{origin}: You need to draw first.".format(
                origin=origin
            ))
            return
        elif e.code == UnoStateError.NO_MORE_DRAWS:
            do_game_over(client, target, "Looks like the pile ran out! ")
            return
        raise

    suffix = ""

    if must_draw > 0:
        suffix = " and had to draw {} cards".format(must_draw)
        client.notice(origin,
                      "You drew: {}".format(" ".join(show_card_irc(card)
                                            for card in game.players[origin][-must_draw:])))

    send_summary(client, target, game, "{origin} passed{suffix}. ".format(
        origin=origin,
        suffix=suffix
    ))
    send_hand(client, game.turn, game)


@service.command(r"!hand")
@requires_context("uno")
def show_hand(client, target, origin):
    """
    Show hand.

    List cards in hand.
    """
    storage = service.storage_for(client.bot)
    game = storage.games[client.name, target]

    if origin not in game.players:
        client.message(target, "{origin}: You're not in this game.".format(
            origin=origin
        ))
        return

    send_hand(client, origin, game)


@service.command(r"!scores")
@requires_context("uno")
def show_hand(client, target, origin):
    """
    Show scores.

    Show scores for all players.
    """
    storage = service.storage_for(client.bot)
    game = storage.games[client.name, target]

    if origin not in game.players:
        client.message(target, "{origin}: You're not in this game.".format(
            origin=origin
        ))
        return

    client.message(target, "Standings: {scores}".format(scores=show_scores(game)))


@service.command(r"!leave")
@requires_context("uno")
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

    client.message(target, "{origin} left the game. Their cards were shuffled back into the pile.".format(
        origin=origin
    ))

    if game.started:
        send_summary(client, target, game)
