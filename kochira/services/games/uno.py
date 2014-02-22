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
def setup_contexts(ctx):
    ctx.storage.games = {}


class UnoStateError(Exception):
    def __init__(self, code):
        self.code = code

    HAS_ALREADY_DRAWN = 0
    MUST_DRAW_FIRST = 1
    NOT_IN_HAND = 2
    CARD_NOT_COMPATIBLE = 3
    NO_MORE_DRAWS = 4
    MUST_STACK = 5


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

        if self.must_draw > 0:
            raise UnoStateError(UnoStateError.MUST_STACK)

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
        self.has_drawn = False

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

        if self.players:
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
        elif rank == Game.SKIP and self.must_draw == 0:
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


def show_scores(ctx, game):
    return ", ".join(ctx._("{player} ({num} cards)").format(player=k, num=len(v))
                     for k, v in game.scores())

def send_summary(ctx, game, prefix=""):
    ctx.message(ctx._("{turn}: {prefix}It's your turn.{stack} Top card ({count} left): {top}").format(
        turn=game.turn,
        prefix=prefix,
        count=len(game.draw_pile),
        stack=ctx._(" Stack a special card or pass and draw {}.").format(game.must_draw) if game.must_draw > 0 else "",
        top=show_card_irc(game.top)
    ))


def send_hand(ctx, player, game):
    ctx.client.notice(player, ctx._("[{target}] Uno: Your hand: {hand}").format(
        target=ctx.target,
        hand=" ".join(show_card_irc(card) for card in game.players[player])
    ))


def do_game_over(ctx, prefix=""):
    game = ctx.storage.games[ctx.client.name, ctx.target]

    ctx.message(prefix + ctx._("Game over! Final results: {results}").format(
        results=show_scores(game)
    ))
    del ctx.storage.games[ctx.client.name, ctx.target]
    ctx.remove_context("uno")


@service.command(r"uno(?: (?P<set>.+))?", mention=True)
@service.command(r"!uno(?: (?P<set>.+))?")
def start_uno(ctx, set=None):
    """
    Start game.

    Start a game of Uno.
    """

    k = (ctx.client.name, ctx.target)

    if k in ctx.storage.games:
        ctx.respond(ctx._("A game is already in progress."))
        return

    if set is not None:
        try:
            set = Game.SETS[set.lower()]
        except:
            ctx.respond(ctx._("I don't know what set \"{set}\" is.").format(
                origin=ctx.origin,
                set=set
            ))
            return

    g = Game(set)
    g.join(ctx.origin)
    ctx.storage.games[k] = g

    ctx.message(ctx._("{origin} has started a game of Uno! Send !join to join, and !deal to deal when ready!").format(
        origin=ctx.origin
    ))

    ctx.add_context("uno")


@service.command(r"!stop")
@requires_context("uno")
def stop_uno(ctx):
    """
    Stop game.

    Stop the Uno game in progress.
    """
    do_game_over(ctx)


@service.command(r"!join")
@requires_context("uno")
def join_uno(ctx):
    """
    Join game.

    Join an Uno game in progress.
    """
    game = ctx.storage.games[ctx.client.name, ctx.target]

    if ctx.origin in game.players:
        ctx.respond(ctx._("You're already in the game."))
        return

    game.join(ctx.origin)

    ctx.message(ctx._("{origin} has joined the game!").format(
        origin=ctx.origin
    ))


@service.command(r"!deal")
@requires_context("uno")
def deal_uno(ctx):
    """
    Deal for game.

    Deal cards to players in game.
    """
    game = ctx.storage.games[ctx.client.name, ctx.target]

    if ctx.origin not in game.players:
        ctx.respond(ctx._("You're not in this game."))
        return

    if game.started:
        ctx.respond(ctx._("This game is already in progress."))
        return

    if len(game.players) < 2:
        ctx.respond(ctx._("There aren't enough players to deal yet."))
        return

    ctx.message(ctx._("The game has started! Players: {players}").format(
        players=", ".join(game.players.keys())
    ))
    game.start()

    send_summary(ctx, game)
    for player in game.players.keys():
        send_hand(ctx, player, game)


@service.command(r"!play (?P<raw_card>\S+)(?: (?P<target_color>.))?")
@requires_context("uno")
def play_card(ctx, raw_card, target_color=None):
    """
    Play card.

    Play an Uno card for the in-progress game.
    """
    game = ctx.storage.games[ctx.client.name, ctx.target]

    if ctx.origin not in game.players:
        ctx.respond(ctx._("You're not in this game."))
        return

    if ctx.origin != game.turn:
        ctx.respond(ctx._("It's not your turn."))
        return

    try:
        card = Game.read_card(raw_card)
    except ValueError:
        ctx.respond(ctx._("I don't know what card that is."))
        return

    color, rank = card

    if target_color is not None and color != Game.WILD:
        ctx.respond(ctx._("That's not a wild card, dumbass."))
        return

    if target_color is None and color == Game.WILD:
        ctx.respond(ctx._("You need to give me a color to change to, e.g.: !play wd4 r"))
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
            ctx.respond(ctx._("You can't play that card right now."))
            return
        elif e.code == UnoStateError.NOT_IN_HAND:
            ctx.respond(ctx._("You don't have that card."))
            return
    except ValueError:
        ctx.respond(ctx._("That's not a valid target color."))
        return

    if game_over:
        do_game_over(ctx)
        return

    if len(game.players[last_turn]) == 1:
        ctx.message(ctx._("{player} has UNO!").format(
            player=last_turn
        ))

    prefix = ""

    if rank == Game.REVERSE:
        prefix = ctx._("Order reversed! ")
    elif rank == Game.DRAW_TWO:
        prefix = ctx._("Draw two! ")
    elif rank == Game.DRAW_FOUR:
        prefix = ctx._("Draw four! ")
    elif rank == Game.SKIP and game.must_draw == 0:
        prefix = ctx._("{player} was skipped! ").format(player=usual_turn)
    elif rank == Game.SKIP:
        prefix = ctx._("{player} passed the stack on! ").format(player=last_turn)

    send_summary(ctx, game, prefix)
    send_hand(ctx, game.turn, game)


@service.command(r"!draw")
@requires_context("uno")
def draw(ctx):
    """
    Draw.

    Draw a card from the pile.
    """
    game = ctx.storage.games[ctx.client.name, ctx.target]

    if ctx.origin not in game.players:
        ctx.respond(ctx._("You're not in this game."))
        return

    if ctx.origin != game.turn:
        ctx.respond(ctx._("It's not your turn."))
        return

    try:
        card = game.turn_draw()
    except UnoStateError as e:
        if e.code == UnoStateError.HAS_ALREADY_DRAWN:
            ctx.respond(ctx._("You've already drawn."))
            return
        elif e.code == UnoStateError.NO_MORE_DRAWS:
            do_game_over(ctx, ctx._("Looks like the pile ran out! "))
            return
        elif e.code == UnoStateError.MUST_STACK:
            ctx.respond(ctx._("You need to stack a card."))
            return
        raise

    ctx.client.notice(ctx.origin, ctx._("[{target}] Uno: You drew: {card}").format(target=ctx.target, card=show_card_irc(card)))
    ctx.message(ctx._("{origin} draws.").format(origin=ctx.origin))


@service.command(r"!pass")
@requires_context("uno")
def pass_(ctx):
    """
    Pass.

    Pass, if a card has been drawn.
    """
    game = ctx.storage.games[ctx.client.name, ctx.target]

    if ctx.origin not in game.players:
        ctx.respond(ctx._("You're not in this game."))
        return

    if ctx.origin != game.turn:
        ctx.respond(ctx._("It's not your turn."))
        return

    must_draw = game.must_draw

    try:
        card = game.turn_pass()
    except UnoStateError as e:
        if e.code == UnoStateError.MUST_DRAW_FIRST:
            ctx.respond(ctx._("You need to draw first."))
            return
        elif e.code == UnoStateError.NO_MORE_DRAWS:
            do_game_over(ctx, ctx._("Looks like the pile ran out! "))
            return
        raise

    suffix = ""

    if must_draw > 0:
        ctx.client.notice(ctx.origin, ctx._("[{target}] Uno: You drew: {cards}").format(
            target=ctx.target,
            cards=" ".join(show_card_irc(card)
                           for card in game.players[ctx.origin][-must_draw:])))

    if must_draw > 0:
        prefix = ctx._("{origin} passed and had to draw {num} cards.".format(
            origin=ctx.origin,
            num=must_draw
        ))
    else:
        prefix = ctx._("{origin} passed.").format(origin=ctx.origin)

    send_summary(ctx, game, prefix)
    send_hand(ctx, game.turn, game)


@service.command(r"!hand")
@requires_context("uno")
def show_hand(ctx):
    """
    Show hand.

    List cards in hand.
    """
    game = ctx.storage.games[ctx.client.name, ctx.target]

    if ctx.origin not in game.players:
        ctx.respond(ctx._("You're not in this game."))
        return

    send_hand(ctx, ctx.origin, game)


@service.command(r"!scores")
@requires_context("uno")
def show_hand(ctx):
    """
    Show scores.

    Show scores for all players.
    """
    game = ctx.storage.games[ctx.client.name, ctx.target]

    if ctx.origin not in game.players:
        ctx.respond(ctx._("You're not in this game."))
        return

    ctx.message(ctx._("Standings: {scores}").format(scores=show_scores(ctx, game)))


@service.command(r"!leave")
@requires_context("uno")
def leave(ctx):
    """
    Leave game.

    Leave the game, if you're participating.
    """
    game = ctx.storage.games[ctx.client.name, ctx.target]

    if ctx.origin not in game.players:
        ctx.respond(ctx._("You're not in this game."))
        return

    game_over = game.leave(ctx.origin)

    if game_over:
        do_game_over(ctx)
        return

    ctx.message(ctx._("{origin} left the game. Their cards were shuffled back into the pile.").format(
        origin=ctx.origin
    ))

    if game.started:
        send_summary(ctx, game)
