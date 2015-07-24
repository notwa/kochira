"""
Say things.

Make me say things!
"""

import inflect
import jinja2
import random

from kochira import config
from kochira.service import Service, Config

service = Service(__name__, __doc__)

@service.config
class Config(Config):
    lexicon_file = config.Field(doc="File to extract the lexicon from, in Moby POS format.", default="mobypos.txt")


PARTS_OF_SPEECH = {
    'N': 'nouns',
    'p': 'plurals',
    'h': 'noun_phrases',
    'V': 'verbs',
    't': 'transitive_verbs',
    'i': 'intransitive_verbs',
    'A': 'adjectives',
    'v': 'adverbs',
    'C': 'conjunctions',
    'P': 'prepositions',
    '!': 'interjections',
    'r': 'pronouns',
    'D': 'definite_articles',
    'I': 'indefinite_articles',
    'o': 'nominatives',
}

def make_lexicon(fn):
    lexicon = {}
    with open(fn, 'rb') as f:
        for line in f:
            word, _, poss = line.decode('utf-8').rstrip().rpartition('\\')
            for pos in poss:
                if pos in PARTS_OF_SPEECH:
                    lexicon.setdefault(PARTS_OF_SPEECH[pos], []).append(word)
    return lexicon


@service.setup
def setup(ctx):
    ctx.storage.inflector = inflect.engine()
    ctx.storage.env = jinja2.Environment(undefined=jinja2.StrictUndefined)
    ctx.storage.env.filters.update({
        k: getattr(ctx.storage.inflector, k)
        for k in ['plural', 'plural_noun', 'plural_verb', 'plural_adj',
                  'singular_noun', 'no', 'num', 'a', 'an', 'present_participle',
                  'ordinal', 'number_to_words']})
    ctx.storage.env.filters['join'] = lambda xs, *a, **kw: ctx.storage.inflector.join(list(xs), *a, **kw)
    ctx.storage.env.filters['choose'] = random.choice
    ctx.storage.env.filters['sample'] = random.sample

    lexicon = make_lexicon(ctx.config.lexicon_file)
    ctx.storage.vars = {}
    ctx.storage.vars.update(lexicon)


@service.command("!say (?P<text>.+)")
def say(ctx, text):
    """
    Say stuff.
    
    I can say things!
    """
    try:
        ctx.message(ctx.storage.env.from_string(text).render(**ctx.storage.vars))
    except Exception as e:
        ctx.respond(ctx._("Didn't manage to say that: {error}").format(error=e))
