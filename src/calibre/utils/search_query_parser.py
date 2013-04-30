#!/usr/bin/env  python
# encoding: utf-8
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
A parser for search queries with a syntax very similar to that used by
the Google search engine.

For details on the search query syntax see :class:`SearchQueryParser`.
To use the parser, subclass :class:`SearchQueryParser` and implement the
methods :method:`SearchQueryParser.universal_set` and
:method:`SearchQueryParser.get_matches`. See for example :class:`Tester`.

If this module is run, it will perform a series of unit tests.
'''

import sys, operator, weakref, re

from calibre.constants import preferred_encoding
from calibre.utils.icu import sort_key
from calibre import prints


'''
This class manages access to the preference holding the saved search queries.
It exists to ensure that unicode is used throughout, and also to permit
adding other fields, such as whether the search is a 'favorite'
'''
class SavedSearchQueries(object):
    queries = {}
    opt_name = ''

    def __init__(self, db, _opt_name):
        self.opt_name = _opt_name;
        if db is not None:
            self.queries = db.prefs.get(self.opt_name, {})
        else:
            self.queries = {}
        try:
            self._db = weakref.ref(db)
        except:
            # db could be None
            self._db = lambda : None

    @property
    def db(self):
        return self._db()

    def force_unicode(self, x):
        if not isinstance(x, unicode):
            x = x.decode(preferred_encoding, 'replace')
        return x

    def add(self, name, value):
        db = self.db
        if db is not None:
            self.queries[self.force_unicode(name)] = self.force_unicode(value).strip()
            db.prefs[self.opt_name] = self.queries

    def lookup(self, name):
        return self.queries.get(self.force_unicode(name), None)

    def delete(self, name):
        db = self.db
        if db is not None:
            self.queries.pop(self.force_unicode(name), False)
            db.prefs[self.opt_name] = self.queries

    def rename(self, old_name, new_name):
        db = self.db
        if db is not None:
            self.queries[self.force_unicode(new_name)] = \
                        self.queries.get(self.force_unicode(old_name), None)
            self.queries.pop(self.force_unicode(old_name), False)
            db.prefs[self.opt_name] = self.queries

    def names(self):
        return sorted(self.queries.keys(),key=sort_key)

'''
Create a global instance of the saved searches. It is global so that the searches
are common across all instances of the parser (devices, library, etc).
'''
ss = SavedSearchQueries(None, None)

def set_saved_searches(db, opt_name):
    global ss
    ss = SavedSearchQueries(db, opt_name)

def saved_searches():
    global ss
    return ss

'''
Parse a search expression into a series of potentially recursive operations.

Note that the interpreter wants binary operators, not n-ary ops. This is why we
recurse instead of iterating when building sequences of the same op.

The syntax is more than a bit twisted. In particular, the handling of colons
in the base token requires semantic analysis.

Also note that the query string is lowercased before analysis. This is OK because
calibre's searches are all case-insensitive.

Grammar:

prog ::= or_expression

or_expression ::= and_expression [ 'or' or_expression ]

and_expression ::= not_expression [ [ 'and' ] and_expression ]

not_expression ::= [ 'not' ] location_expression

location_expression ::= base_token | ( '(' or_expression ')' )

base_token ::= a sequence of letters and colons, perhaps quoted
'''
class Parser(object):

        def __init__(self):
            self.current_token = 0
            self.tokens = None

        OPCODE = 1
        WORD = 2
        QUOTED_WORD = 3
        EOF = 4

        # Had to translate named constants to numeric values
        lex_scanner = re.Scanner([
                (r'[()]',             lambda x,t: (1, t)),
                (r'[^"()\s]+',        lambda x,t: (2, unicode(t))),
                (r'".*?((?<!\\)")',   lambda x,t: (3, t[1:-1])),
                (r'\s+',              None)
        ], flags=re.DOTALL)

        def token(self, advance=False):
            if self.is_eof():
                return None
            res = self.tokens[self.current_token][1]
            if advance:
                self.current_token += 1
            return res

        def lcase_token(self, advance=False):
            if self.is_eof():
                return None
            res = self.tokens[self.current_token][1]
            if advance:
                self.current_token += 1
            return icu_lower(res)

        def token_type(self):
            if self.is_eof():
                return self.EOF
            return self.tokens[self.current_token][0]

        def is_eof(self):
            return self.current_token >= len(self.tokens)

        def advance(self):
            self.current_token += 1

        def parse(self, expr, locations):
            self.locations = locations
            self.tokens = self.lex_scanner.scan(expr)[0]
            self.current_token = 0
            prog = self.or_expression()
            if not self.is_eof():
                raise ParseException(_('Extra characters at end of search'))
            #prints(self.tokens, '\n', prog)
            return prog

        def or_expression(self):
            lhs = self.and_expression()
            if self.lcase_token() == 'or':
                self.advance()
                return ['or', lhs, self.or_expression()]
            return lhs

        def and_expression(self):
            lhs = self.not_expression()
            if self.lcase_token() == 'and':
                self.advance()
                return ['and', lhs, self.and_expression()]

            # Account for the optional 'and'
            if (self.token_type() in [self.WORD, self.QUOTED_WORD] and
                            self.lcase_token() != 'or'):
                return ['and', lhs, self.and_expression()]
            return lhs

        def not_expression(self):
            if self.lcase_token() == 'not':
                self.advance()
                return ['not', self.not_expression()]
            return self.location_expression()

        def location_expression(self):
            if self.token() == '(':
                self.advance()
                res = self.or_expression()
                if self.token(advance=True) != ')':
                    raise ParseException(_('missing )'))
                return res
            if self.token_type() not in [ self.WORD, self.QUOTED_WORD ]:
                raise ParseException(_('Invalid syntax. Expected a lookup name or a word'))

            return self.base_token()

        def base_token(self):
            if self.token_type() == self.QUOTED_WORD:
                return ['token', 'all', self.token(advance=True)]

            words = self.token(advance=True).split(':')

            # The complexity here comes from having colon-separated search
            # values. That forces us to check that the first "word" in a colon-
            # separated group is a valid location. If not, then the token must
            # be reconstructed. We also have the problem that locations can be
            # followed by quoted strings that appear as the next token. and that
            # tokens can be a sequence of colons.

            # We have a location if there is more than one word and the first
            # word is in locations. This check could produce a "wrong" answer if
            # the search string is something like 'author: "foo"' because it
            # will be interpreted as 'author:"foo"'. I am choosing to accept the
            # possible error. The expression should be written '"author:" foo'
            if len(words) > 1 and words[0] in self.locations:
                loc = words[0]
                words = words[1:]
                if len(words) == 1 and self.token_type() == self.QUOTED_WORD:
                    return ['token', loc, self.token(advance=True)]
                return ['token', icu_lower(loc), ':'.join(words)]

            return ['token', 'all', ':'.join(words)]

class ParseException(Exception):

    @property
    def msg(self):
        if len(self.args) > 0:
            return self.args[0]
        return ""

class SearchQueryParser(object):
    '''
    Parses a search query.

    A search query consists of tokens. The tokens can be combined using
    the `or`, `and` and `not` operators as well as grouped using parentheses.
    When no operator is specified between two tokens, `and` is assumed.

    Each token is a string of the form `location:query`. `location` is a string
    from :member:`DEFAULT_LOCATIONS`. It is optional. If it is omitted, it is assumed to
    be `all`. `query` is an arbitrary string that must not contain parentheses.
    If it contains whitespace, it should be quoted by enclosing it in `"` marks.

    Examples::

      * `Asimov` [search for the string "Asimov" in location `all`]
      * `comments:"This is a good book"` [search for "This is a good book" in `comments`]
      * `author:Asimov tag:unread` [search for books by Asimov that have been tagged as unread]
      * `author:Asimov or author:Hardy` [search for books by Asimov or Hardy]
      * `(author:Asimov or author:Hardy) and not tag:read` [search for unread books by Asimov or Hardy]
    '''


    @staticmethod
    def run_tests(parser, result, tests):
        failed = []
        for test in tests:
            prints('\tTesting:', test[0], end=' ')
            res = parser.parseString(test[0])
            if list(res.get(result, None)) == test[1]:
                print 'OK'
            else:
                print 'FAILED:', 'Expected:', test[1], 'Got:', list(res.get(result, None))
                failed.append(test[0])
        return failed

    def __init__(self, locations, test=False, optimize=False):
        self.sqp_initialize(locations, test=test, optimize=optimize)
        self.parser = Parser()

    def sqp_change_locations(self, locations):
        self.sqp_initialize(locations, optimize=self.optimize)

    def sqp_initialize(self, locations, test=False, optimize=False):
        self.locations = locations
        self._tests_failed = False
        self.optimize = optimize

    def parse(self, query):
        # empty the list of searches used for recursion testing
        self.recurse_level = 0
        self.searches_seen = set([])
        candidates = self.universal_set()
        return self._parse(query, candidates)

    # this parse is used internally because it doesn't clear the
    # recursive search test list. However, we permit seeing the
    # same search a few times because the search might appear within
    # another search.
    def _parse(self, query, candidates=None):
        self.recurse_level += 1
        try:
            res = self.parser.parse(query, self.locations)
        except RuntimeError:
            raise ParseException(_('Failed to parse query, recursion limit reached: %s')%repr(query))
        if candidates is None:
            candidates = self.universal_set()
        t = self.evaluate(res, candidates)
        self.recurse_level -= 1
        return t

    def method(self, group_name):
        return getattr(self, 'evaluate_'+group_name)

    def evaluate(self, parse_result, candidates):
        return self.method(parse_result[0])(parse_result[1:], candidates)

    def evaluate_and(self, argument, candidates):
        # RHS checks only those items matched by LHS
        # returns result of RHS check: RHmatches(LHmatches(c))
        #  return self.evaluate(argument[0]).intersection(self.evaluate(argument[1]))
        l = self.evaluate(argument[0], candidates)
        return l.intersection(self.evaluate(argument[1], l))

    def evaluate_or(self, argument, candidates):
        # RHS checks only those elements not matched by LHS
        # returns LHS union RHS: LHmatches(c) + RHmatches(c-LHmatches(c))
        #  return self.evaluate(argument[0]).union(self.evaluate(argument[1]))
        l = self.evaluate(argument[0], candidates)
        return l.union(self.evaluate(argument[1], candidates.difference(l)))

    def evaluate_not(self, argument, candidates):
        # unary op checks only candidates. Result: list of items matching
        # returns: c - matches(c)
        #  return self.universal_set().difference(self.evaluate(argument[0]))
        return candidates.difference(self.evaluate(argument[0], candidates))

#     def evaluate_parenthesis(self, argument, candidates):
#         return self.evaluate(argument[0], candidates)

    def evaluate_token(self, argument, candidates):
        location = argument[0]
        query = argument[1]
        if location.lower() == 'search':
            if query.startswith('='):
                query = query[1:]
            try:
                if query in self.searches_seen:
                    raise ParseException(_('Recursive saved search: {0}').format(query))
                if self.recurse_level > 5:
                    self.searches_seen.add(query)
                return self._parse(saved_searches().lookup(query), candidates)
            except ParseException as e:
                raise e
            except: # convert all exceptions (e.g., missing key) to a parse error
                import traceback
                traceback.print_exc()
                raise ParseException(_('Unknown error in saved search: {0}').format(query))
        return self._get_matches(location, query, candidates)

    def _get_matches(self, location, query, candidates):
        if self.optimize:
            return self.get_matches(location, query, candidates=candidates)
        else:
            return self.get_matches(location, query)

    def get_matches(self, location, query, candidates=None):
        '''
        Should return the set of matches for :param:'location` and :param:`query`.

        The search must be performed over all entries if :param:`candidates` is
        None otherwise only over the items in candidates.

        :param:`location` is one of the items in :member:`SearchQueryParser.DEFAULT_LOCATIONS`.
        :param:`query` is a string literal.
        :return: None or a subset of the set returned by :meth:`universal_set`.
        '''
        return set([])

    def universal_set(self):
        '''
        Should return the set of all matches.
        '''
        return set([])

# Testing {{{

class Tester(SearchQueryParser):

    texts = {
 1: [u'Eugenie Grandet', u'Honor\xe9 de Balzac', u'manybooks.net', u'lrf'],
 2: [u'Fanny Hill', u'John Cleland', u'manybooks.net', u'lrf'],
 3: [u'Persuasion', u'Jane Austen', u'manybooks.net', u'lrf'],
 4: [u'Psmith, Journalist', u'P. G. Wodehouse', u'Some Publisher', u'lrf'],
 5: [u'The Complete Works of William Shakespeare',
     u'William Shakespeare',
     u'manybooks.net',
     u'lrf'],
 6: [u'The History of England, Volume I',
     u'David Hume',
     u'manybooks.net',
     u'lrf'],
 7: [u'Someone Comes to Town, Someone Leaves Town',
     u'Cory Doctorow',
     u'Tor Books',
     u'lrf'],
 8: [u'Stalky and Co.', u'Rudyard Kipling', u'manybooks.net', u'lrf'],
 9: [u'A Game of Thrones', u'George R. R. Martin', None, u'lrf,rar'],
 10: [u'A Clash of Kings', u'George R. R. Martin', None, u'lrf,rar'],
 11: [u'A Storm of Swords', u'George R. R. Martin', None, u'lrf,rar'],
 12: [u'Biggles - Pioneer Air Fighter', u'W. E. Johns', None, u'lrf,rtf'],
 13: [u'Biggles of the Camel Squadron',
      u'W. E. Johns',
      u'London:Thames, (1977)',
      u'lrf,rtf'],
 14: [u'A Feast for Crows', u'George R. R. Martin', None, u'lrf,rar'],
 15: [u'Cryptonomicon', u'Neal Stephenson', None, u'lrf,rar'],
 16: [u'Quicksilver', u'Neal Stephenson', None, u'lrf,zip'],
 17: [u'The Comedies of William Shakespeare',
      u'William Shakespeare',
      None,
      u'lrf'],
 18: [u'The Histories of William Shakespeare',
      u'William Shakespeare',
      None,
      u'lrf'],
 19: [u'The Tragedies of William Shakespeare',
      u'William Shakespeare',
      None,
      u'lrf'],
 20: [u'An Ideal Husband', u'Oscar Wilde', u'manybooks.net', u'lrf'],
 21: [u'Flight of the Nighthawks', u'Raymond E. Feist', None, u'lrf,rar'],
 22: [u'Into a Dark Realm', u'Raymond E. Feist', None, u'lrf,rar'],
 23: [u'The Sundering', u'Walter Jon Williams', None, u'lrf,rar'],
 24: [u'The Praxis', u'Walter Jon Williams', None, u'lrf,rar'],
 25: [u'Conventions of War', u'Walter Jon Williams', None, u'lrf,rar'],
 26: [u'Banewreaker', u'Jacqueline Carey', None, u'lrf,rar'],
 27: [u'Godslayer', u'Jacqueline Carey', None, u'lrf,rar'],
 28: [u"Kushiel's Scion", u'Jacqueline Carey', None, u'lrf,rar'],
 29: [u'Underworld', u'Don DeLillo', None, u'lrf,rar'],
 30: [u'Genghis Khan and The Making of the Modern World',
      u'Jack Weatherford Orc',
      u'Three Rivers Press',
      u'lrf,zip'],
 31: [u'The Best and the Brightest',
      u'David Halberstam',
      u'Modern Library',
      u'lrf,zip'],
 32: [u'The Killer Angels', u'Michael Shaara', None, u'html,lrf'],
 33: [u'Band Of Brothers', u'Stephen E Ambrose', None, u'lrf,txt'],
 34: [u'The Gates of Rome', u'Conn Iggulden', None, u'lrf,rar'],
 35: [u'The Death of Kings', u'Conn Iggulden', u'Bantam Dell', u'lit,lrf'],
 36: [u'The Field of Swords', u'Conn Iggulden', None, u'lrf,rar'],
 37: [u'Masterman Ready', u'Marryat, Captain Frederick', None, u'lrf'],
 38: [u'With the Lightnings',
      u'David Drake',
      u'Baen Publishing Enterprises',
      u'lit,lrf'],
 39: [u'Lt. Leary, Commanding',
      u'David Drake',
      u'Baen Publishing Enterprises',
      u'lit,lrf'],
 40: [u'The Far Side of The Stars',
      u'David Drake',
      u'Baen Publishing Enterprises',
      u'lrf,rar'],
 41: [u'The Way to Glory',
      u'David Drake',
      u'Baen Publishing Enterprises',
      u'lrf,rar'],
 42: [u'Some Golden Harbor', u'David Drake', u'Baen Books', u'lrf,rar'],
 43: [u'Harry Potter And The Half-Blood Prince',
      u'J. K. Rowling',
      None,
      u'lrf,rar'],
 44: [u'Harry Potter and the Order of the Phoenix',
      u'J. K. Rowling',
      None,
      u'lrf,rtf'],
 45: [u'The Stars at War', u'David Weber , Steve White', None, u'lrf,rtf'],
 46: [u'The Stars at War II',
      u'Steve White',
      u'Baen Publishing Enterprises',
      u'lrf,rar'],
 47: [u'Exodus', u'Steve White,Shirley Meier', u'Baen Books', u'lrf,rar'],
 48: [u'Harry Potter and the Goblet of Fire',
      u'J. K. Rowling',
      None,
      u'lrf,rar'],
 49: [u'Harry Potter and the Prisoner of Azkaban',
      u'J. K. Rowling',
      None,
      u'lrf,rtf'],
 50: [u'Harry Potter and the Chamber of Secrets',
      u'J. K. Rowling',
      None,
      u'lit,lrf'],
 51: [u'Harry Potter and the Deathly Hallows',
      u'J.K. Rowling',
      None,
      u'lit,lrf,pdf'],
 52: [u"His Majesty's Dragon", u'Naomi Novik', None, u'lrf,rar'],
 53: [u'Throne of Jade', u'Naomi Novik', u'Del Rey', u'lit,lrf'],
 54: [u'Black Powder War', u'Naomi Novik', u'Del Rey', u'lrf,rar'],
 55: [u'War and Peace', u'Leo Tolstoy', u'gutenberg.org', u'lrf,txt'],
 56: [u'Anna Karenina', u'Leo Tolstoy', u'gutenberg.org', u'lrf,txt'],
 57: [u'A Shorter History of Rome',
      u'Eugene Lawrence,Sir William Smith',
      u'gutenberg.org',
      u'lrf,zip'],
 58: [u'The Name of the Rose', u'Umberto Eco', None, u'lrf,rar'],
 71: [u"Wind Rider's Oath", u'David Weber', u'Baen', u'lrf'],
 74: [u'Rally Cry', u'William R Forstchen', None, u'htm,lrf'],
 86: [u'Empire of Ivory', u'Naomi Novik', None, u'lrf,rar'],
 87: [u"Renegade's Magic", u'Robin Hobb', None, u'lrf,rar'],
 89: [u'Master and commander',
      u"Patrick O'Brian",
      u'Fontana,\n1971',
      u'lit,lrf'],
 91: [u'A Companion to Wolves',
      u'Sarah Monette,Elizabeth Beär',
      None,
      u'lrf,rar'],
 92: [u'The Lions of al-Rassan', u'Guy Gavriel Kay', u'Eos', u'lit,lrf'],
 93: [u'Gardens of the Moon', u'Steven Erikson', u'Tor Fantasy', u'lit,lrf'],
 95: [u'The Master and Margarita',
      u'Mikhail Bulgakov',
      u'N.Y. : Knopf, 1992.',
      u'lrf,rtf'],
 120: [u'Deadhouse Gates',
       u'Steven Erikson',
       u'London : Bantam Books, 2001.',
       u'lit,lrf'],
 121: [u'Memories of Ice', u'Steven Erikson', u'Bantam Books', u'lit,lrf'],
 123: [u'House of Chains', u'Steven Erikson', u'Bantam Books', u'lit,lrf'],
 125: [u'Midnight Tides', u'Steven Erikson', u'Bantam Books', u'lit,lrf'],
 126: [u'The Bonehunters', u'Steven Erikson', u'Bantam Press', u'lit,lrf'],
 129: [u'Guns, germs, and steel: the fates of human societies',
       u'Jared Diamond',
       u'New York : W.W. Norton, c1997.',
       u'lit,lrf'],
 136: [u'Wildcards', u'George R. R. Martin', None, u'html,lrf'],
 138: [u'Off Armageddon Reef', u'David Weber', u'Tor Books', u'lit,lrf'],
 144: [u'Atonement',
       u'Ian McEwan',
       u'New York : Nan A. Talese/Doubleday, 2002.',
       u'lrf,rar'],
 146: [u'1632', u'Eric Flint', u'Baen Books', u'lit,lrf'],
 147: [u'1633', u'David Weber,Eric Flint,Dru Blair', u'Baen', u'lit,lrf'],
 148: [u'1634: The Baltic War',
       u'David Weber,Eric Flint',
       u'Baen',
       u'lit,lrf'],
 150: [u'The Dragonbone Chair', u'Tad Williams', u'DAW Trade', u'lrf,rtf'],
 152: [u'The Little Book That Beats the Market',
       u'Joel Greenblatt',
       u'Wiley',
       u'epub,lrf'],
 153: [u'Pride of Carthage', u'David Anthony Durham', u'Anchor', u'lit,lrf'],
 154: [u'Stone of farewell',
       u'Tad Williams',
       u'New York : DAW Books, 1990.',
       u'lrf,txt'],
 166: [u'American Gods', u'Neil Gaiman', u'HarperTorch', u'lit,lrf'],
 176: [u'Pillars of the Earth',
       u'Ken Follett',
       u'New American Library',
       u'lit,lrf'],
 182: [u'The Eye of the world',
       u'Robert Jordan',
       u'New York : T. Doherty Associates, c1990.',
       u'lit,lrf'],
 188: [u'The Great Hunt', u'Robert Jordan', u'ATOM', u'lrf,zip'],
 189: [u'The Dragon Reborn', u'Robert Jordan', None, u'lit,lrf'],
 190: [u'The Shadow Rising', u'Robert Jordan', None, u'lit,lrf'],
 191: [u'The Fires of Heaven',
       u'Robert Jordan',
       u'Time Warner Books Uk',
       u'lit,lrf'],
 216: [u'Lord of chaos',
       u'Robert Jordan',
       u'New York : TOR, c1994.',
       u'lit,lrf'],
 217: [u'A Crown of Swords', u'Robert Jordan', None, u'lit,lrf'],
 236: [u'The Path of Daggers', u'Robert Jordan', None, u'lit,lrf'],
 238: [u'The Client',
       u'John Grisham',
       u'New York : Island, 1994, c1993.',
       u'lit,lrf'],
 240: [u"Winter's Heart", u'Robert Jordan', None, u'lit,lrf'],
 242: [u'In the Beginning was the Command Line',
       u'Neal Stephenson',
       None,
       u'lrf,txt'],
 249: [u'Crossroads of Twilight', u'Robert Jordan', None, u'lit,lrf'],
 251: [u'Caves of Steel', u'Isaac Asimov', u'Del Rey', u'lrf,zip'],
 253: [u"Hunter's Run",
       u'George R. R. Martin,Gardner Dozois,Daniel Abraham',
       u'Eos',
       u'lrf,rar'],
 257: [u'Knife of Dreams', u'Robert Jordan', None, u'lit,lrf'],
 258: [u'Saturday',
       u'Ian McEwan',
       u'London : Jonathan Cape, 2005.',
       u'lrf,txt'],
 259: [u'My name is Red',
       u'Orhan Pamuk; translated from the Turkish by Erda\u011f G\xf6knar',
       u'New York : Alfred A. Knopf, 2001.',
       u'lit,lrf'],
 265: [u'Harbinger', u'David Mack', u'Star Trek', u'lit,lrf'],
 267: [u'Summon the Thunder',
       u'Dayton Ward,Kevin Dilmore',
       u'Pocket Books',
       u'lit,lrf'],
 268: [u'Shalimar the Clown',
       u'Salman Rushdie',
       u'New York : Random House, 2005.',
       u'lit,lrf'],
 269: [u'Reap the Whirlwind', u'David Mack', u'Star Trek', u'lit,lrf'],
 272: [u'Mistborn', u'Brandon Sanderson', u'Tor Fantasy', u'lrf,rar'],
 273: [u'The Thousandfold Thought',
       u'R. Scott Bakker',
       u'Overlook TP',
       u'lrf,rtf'],
 276: [u'Elantris',
       u'Brandon Sanderson',
       u'New York : Tor, 2005.',
       u'lrf,rar'],
 291: [u'Sundiver',
       u'David Brin',
       u'New York : Bantam Books, 1995.',
       u'lit,lrf'],
 299: [u'Imperium', u'Robert Harris', u'Arrow', u'lrf,rar'],
 300: [u'Startide Rising', u'David Brin', u'Bantam', u'htm,lrf'],
 301: [u'The Uplift War', u'David Brin', u'Spectra', u'lit,lrf'],
 304: [u'Brightness Reef', u'David Brin', u'Orbit', u'lrf,rar'],
 305: [u"Infinity's Shore", u'David Brin', u'Spectra', u'txt'],
 306: [u"Heaven's Reach", u'David Brin', u'Spectra', u'lrf,rar'],
 325: [u"Foundation's Triumph", u'David Brin', u'Easton Press', u'lit,lrf'],
 327: [u'I am Charlotte Simmons', u'Tom Wolfe', u'Vintage', u'htm,lrf'],
 335: [u'The Currents of Space', u'Isaac Asimov', None, u'lit,lrf'],
 340: [u'The Other Boleyn Girl',
       u'Philippa Gregory',
       u'Touchstone',
       u'lit,lrf'],
 341: [u"Old Man's War", u'John Scalzi', u'Tor', u'htm,lrf'],
 342: [u'The Ghost Brigades',
       u'John Scalzi',
       u'Tor Science Fiction',
       u'html,lrf'],
 343: [u'The Last Colony', u'John Scalzi', u'Tor Books', u'html,lrf'],
 344: [u'Gossip Girl', u'Cecily von Ziegesar', u'Warner Books', u'lrf,rtf'],
 347: [u'Little Brother', u'Cory Doctorow', u'Tor Teen', u'lrf'],
 348: [u'The Reality Dysfunction',
       u'Peter F. Hamilton',
       u'Pan MacMillan',
       u'lit,lrf'],
 353: [u'A Thousand Splendid Suns',
       u'Khaled Hosseini',
       u'Center Point Large Print',
       u'lit,lrf'],
 354: [u'Amsterdam', u'Ian McEwan', u'Anchor', u'lrf,txt'],
 355: [u'The Neutronium Alchemist',
       u'Peter F. Hamilton',
       u'Aspect',
       u'lit,lrf'],
 356: [u'The Naked God', u'Peter F. Hamilton', u'Aspect', u'lit,lrf'],
 421: [u'A Shadow in Summer', u'Daniel Abraham', u'Tor Fantasy', u'lrf,rar'],
 427: [u'Lonesome Dove', u'Larry McMurtry', None, u'lit,lrf'],
 440: [u'Ghost', u'John Ringo', u'Baen', u'lit,lrf'],
 441: [u'Kildar', u'John Ringo', u'Baen', u'lit,lrf'],
 443: [u'Hidden Empire ', u'Kevin J. Anderson', u'Aspect', u'lrf,rar'],
 444: [u'The Gun Seller',
       u'Hugh Laurie',
       u'Washington Square Press',
       u'lrf,rar']
 }

    tests = {
             'Dysfunction' : set([348]),
             'title:Dysfunction' : set([348]),
             'title:Dysfunction OR author:Laurie': set([348, 444]),
             '(tag:txt or tag:pdf)': set([33, 258, 354, 305, 242, 51, 55, 56, 154]),
             '(tag:txt OR tag:pdf) and author:Tolstoy': set([55, 56]),
             'Tolstoy txt': set([55, 56]),
             'Hamilton Amsterdam' : set([]),
             u'Beär' : set([91]),
             'dysfunc or tolstoy': set([348, 55, 56]),
             'tag:txt AND NOT tolstoy': set([33, 258, 354, 305, 242, 154]),
             'not tag:lrf' : set([305]),
             'london:thames': set([13]),
             'publisher:london:thames': set([13]),
             '"(1977)"': set([13]),
             'jack weatherford orc': set([30]),
             }
    fields = {'title':0, 'author':1, 'publisher':2, 'tag':3}

    _universal_set = set(texts.keys())

    def universal_set(self):
        return self._universal_set

    def get_matches(self, location, query, candidates=None):
        location = location.lower()
        if location in self.fields.keys():
            getter = operator.itemgetter(self.fields[location])
        elif location == 'all':
            getter = lambda y: ''.join(x if x else '' for x in y)
        else:
            getter = lambda x: ''

        if not query:
            return set([])
        query = query.lower()
        if candidates:
            return set(key for key, val in self.texts.items() \
                if key in candidates and query and query
                        in getattr(getter(val), 'lower', lambda : '')())
        else:
            return set(key for key, val in self.texts.items() \
                if query and query in getattr(getter(val), 'lower', lambda : '')())



    def run_tests(self):
        failed = []
        for query in self.tests.keys():
            prints('Testing query:', query, end=' ')
            res = self.parse(query)
            if res != self.tests[query]:
                print 'FAILED', 'Expected:', self.tests[query], 'Got:', res
                failed.append(query)
            else:
                print 'OK'
        return failed


def main(args=sys.argv):
    print 'testing unoptimized'
    tester = Tester(['authors', 'author', 'series', 'formats', 'format',
        'publisher', 'rating', 'tags', 'tag', 'comments', 'comment', 'cover',
        'isbn', 'ondevice', 'pubdate', 'size', 'date', 'title', u'#read',
        'all', 'search'], test=True)
    failed = tester.run_tests()
    if tester._tests_failed or failed:
        print '>>>>>>>>>>>>>> Tests Failed <<<<<<<<<<<<<<<'
        return 1

    print '\n\ntesting optimized'
    tester = Tester(['authors', 'author', 'series', 'formats', 'format',
        'publisher', 'rating', 'tags', 'tag', 'comments', 'comment', 'cover',
        'isbn', 'ondevice', 'pubdate', 'size', 'date', 'title', u'#read',
        'all', 'search'], test=True, optimize=True)
    failed = tester.run_tests()
    if tester._tests_failed or failed:
        print '>>>>>>>>>>>>>> Tests Failed <<<<<<<<<<<<<<<'
        return 1

    return 0

if __name__ == '__main__':
    sys.exit(main())

# }}}

