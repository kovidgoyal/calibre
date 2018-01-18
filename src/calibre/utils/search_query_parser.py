#!/usr/bin/env  python2
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

import weakref, re

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
        self.opt_name = _opt_name
        if db is not None:
            db = db.new_api
            self._db = weakref.ref(db)
            self.queries = db.pref(self.opt_name, {})
        else:
            self.queries = {}
            self._db = lambda : None

    @property
    def db(self):
        return self._db()

    def save_queries(self):
        db = self.db
        if db is not None:
            db.set_pref(self.opt_name, self.queries)

    def force_unicode(self, x):
        if not isinstance(x, unicode):
            x = x.decode(preferred_encoding, 'replace')
        return x

    def add(self, name, value):
        self.queries[self.force_unicode(name)] = self.force_unicode(value).strip()
        self.save_queries()

    def lookup(self, name):
        return self.queries.get(self.force_unicode(name), None)

    def delete(self, name):
        self.queries.pop(self.force_unicode(name), False)
        self.save_queries()

    def rename(self, old_name, new_name):
        self.queries[self.force_unicode(new_name)] = \
                    self.queries.get(self.force_unicode(old_name), None)
        self.queries.pop(self.force_unicode(old_name), False)
        self.save_queries()

    def set_all(self, smap):
        self.queries = smap
        self.save_queries()

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


def global_lookup_saved_search(name):
    return ss.lookup(name)


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
            (r'[()]', lambda x,t: (1, t)),
            (r'@.+?:[^")\s]+', lambda x,t: (2, unicode(t))),
            (r'[^"()\s]+', lambda x,t: (2, unicode(t))),
            (r'".*?((?<!\\)")', lambda x,t: (3, t[1:-1])),
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

        # Strip out escaped backslashes, quotes and parens so that the
        # lex scanner doesn't get confused. We put them back later.
        expr = expr.replace(u'\\\\', u'\x01').replace(u'\\"', u'\x02')
        expr = expr.replace(u'\\(', u'\x03').replace(u'\\)', u'\x04')
        self.tokens = self.lex_scanner.scan(expr)[0]
        for (i,tok) in enumerate(self.tokens):
            tt, tv = tok
            if tt == self.WORD or tt == self.QUOTED_WORD:
                self.tokens[i] = (tt,
                    tv.replace(u'\x01', u'\\').replace(u'\x02', u'"').
                    replace(u'\x03', u'(').replace(u'\x04', u')'))

        self.current_token = 0
        prog = self.or_expression()
        if not self.is_eof():
            raise ParseException(_('Extra characters at end of search'))
        # prints(self.tokens, '\n', prog)
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
        if self.token_type() == self.OPCODE and self.token() == '(':
            self.advance()
            res = self.or_expression()
            if self.token_type() != self.OPCODE or self.token(advance=True) != ')':
                raise ParseException(_('missing )'))
            return res
        if self.token_type() not in (self.WORD, self.QUOTED_WORD):
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
        if len(words) > 1 and words[0].lower() in self.locations:
            loc = words[0].lower()
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

    def __init__(self, locations, test=False, optimize=False, lookup_saved_search=None, parse_cache=None):
        self.sqp_initialize(locations, test=test, optimize=optimize)
        self.parser = Parser()
        self.lookup_saved_search = global_lookup_saved_search if lookup_saved_search is None else lookup_saved_search
        self.sqp_parse_cache = parse_cache

    def sqp_change_locations(self, locations):
        self.sqp_initialize(locations, optimize=self.optimize)
        if self.sqp_parse_cache is not None:
            self.sqp_parse_cache.clear()

    def sqp_initialize(self, locations, test=False, optimize=False):
        self.locations = locations
        self._tests_failed = False
        self.optimize = optimize

    def parse(self, query, candidates=None):
        # empty the list of searches used for recursion testing
        self.recurse_level = 0
        self.searches_seen = set([])
        candidates = self.universal_set()
        return self._parse(query, candidates=candidates)

    # this parse is used internally because it doesn't clear the
    # recursive search test list. However, we permit seeing the
    # same search a few times because the search might appear within
    # another search.
    def _parse(self, query, candidates=None):
        self.recurse_level += 1
        try:
            res = self.sqp_parse_cache.get(query, None)
        except AttributeError:
            res = None
        if res is None:
            try:
                res = self.parser.parse(query, self.locations)
            except RuntimeError:
                raise ParseException(_('Failed to parse query, recursion limit reached: %s')%repr(query))
            if self.sqp_parse_cache is not None:
                self.sqp_parse_cache[query] = res
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
                ss = self.lookup_saved_search(query)
                if ss is None:
                    raise ParseException(_('Unknown saved search: {}').format(query))
                return self._parse(ss, candidates)
            except ParseException as e:
                raise e
            except:  # convert all exceptions (e.g., missing key) to a parse error
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
