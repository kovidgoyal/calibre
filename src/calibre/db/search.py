#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re
from functools import partial
from datetime import timedelta

from calibre.utils.config_base import prefs
from calibre.utils.date import parse_date, UNDEFINED_DATE, now
from calibre.utils.icu import primary_find
from calibre.utils.search_query_parser import SearchQueryParser, ParseException

# TODO: Thread safety of saved searches
CONTAINS_MATCH = 0
EQUALS_MATCH   = 1
REGEXP_MATCH   = 2

# Utils {{{

def force_to_bool(val):
    if isinstance(val, (str, unicode)):
        try:
            val = icu_lower(val)
            if not val:
                val = None
            elif val in [_('yes'), _('checked'), 'true', 'yes']:
                val = True
            elif val in [_('no'), _('unchecked'), 'false', 'no']:
                val = False
            else:
                val = bool(int(val))
        except:
            val = None
    return val

def _matchkind(query):
    matchkind = CONTAINS_MATCH
    if (len(query) > 1):
        if query.startswith('\\'):
            query = query[1:]
        elif query.startswith('='):
            matchkind = EQUALS_MATCH
            query = query[1:]
        elif query.startswith('~'):
            matchkind = REGEXP_MATCH
            query = query[1:]

    if matchkind != REGEXP_MATCH:
        # leave case in regexps because it can be significant e.g. \S \W \D
        query = icu_lower(query)
    return matchkind, query

def _match(query, value, matchkind, use_primary_find_in_search=True):
    if query.startswith('..'):
        query = query[1:]
        sq = query[1:]
        internal_match_ok = True
    else:
        internal_match_ok = False
    for t in value:
        try:     ### ignore regexp exceptions, required because search-ahead tries before typing is finished
            t = icu_lower(t)
            if (matchkind == EQUALS_MATCH):
                if internal_match_ok:
                    if query == t:
                        return True
                    comps = [c.strip() for c in t.split('.') if c.strip()]
                    for comp in comps:
                        if sq == comp:
                            return True
                elif query[0] == '.':
                    if t.startswith(query[1:]):
                        ql = len(query) - 1
                        if (len(t) == ql) or (t[ql:ql+1] == '.'):
                            return True
                elif query == t:
                    return True
            elif matchkind == REGEXP_MATCH:
                if re.search(query, t, re.I|re.UNICODE):
                    return True
            elif matchkind == CONTAINS_MATCH:
                if use_primary_find_in_search:
                    if primary_find(query, t)[0] != -1:
                        return True
                elif query in t:
                        return True
        except re.error:
            pass
    return False
# }}}

class DateSearch(object): # {{{

    def __init__(self):
        self.operators = {
            '='   : (1, self.eq),
            '!='  : (2, self.ne),
            '>'   : (1, self.gt),
            '>='  : (2, self.ge),
            '<'   : (1, self.lt),
            '<='  : (2, self.le),
        }
        self.local_today         = { '_today', 'today', icu_lower(_('today')) }
        self.local_yesterday     = { '_yesterday', 'yesterday', icu_lower(_('yesterday')) }
        self.local_thismonth     = { '_thismonth', 'thismonth', icu_lower(_('thismonth')) }
        self.daysago_pat = re.compile(r'(%s|daysago|_daysago)$'%_('daysago'))

    def eq(self, dbdate, query, field_count):
        if dbdate.year == query.year:
            if field_count == 1:
                return True
            if dbdate.month == query.month:
                if field_count == 2:
                    return True
                return dbdate.day == query.day
        return False

    def ne(self, *args):
        return not self.eq(*args)

    def gt(self, dbdate, query, field_count):
        if dbdate.year > query.year:
            return True
        if field_count > 1 and dbdate.year == query.year:
            if dbdate.month > query.month:
                return True
            return (field_count == 3 and dbdate.month == query.month and
                    dbdate.day > query.day)
        return False

    def le(self, *args):
        return not self.gt(*args)

    def lt(self, dbdate, query, field_count):
        if dbdate.year < query.year:
            return True
        if field_count > 1 and dbdate.year == query.year:
            if dbdate.month < query.month:
                return True
            return (field_count == 3 and dbdate.month == query.month and
                    dbdate.day < query.day)
        return False

    def ge(self, *args):
        return not self.lt(*args)

    def __call__(self, query, field_iter):
        matches = set()
        if len(query) < 2:
            return matches

        if query == 'false':
            for v, book_ids in field_iter():
                if isinstance(v, (str, unicode)):
                    v = parse_date(v)
                if v is None or v <= UNDEFINED_DATE:
                    matches |= book_ids
            return matches

        if query == 'true':
            for v, book_ids in field_iter():
                if isinstance(v, (str, unicode)):
                    v = parse_date(v)
                if v is not None and v > UNDEFINED_DATE:
                    matches |= book_ids
            return matches

        relop = None
        for k, op in self.operators.iteritems():
            if query.startswith(k):
                p, relop = op
                query = query[p:]
        if relop is None:
            relop = self.operators['='][-1]

        if query in self.local_today:
            qd = now()
            field_count = 3
        elif query in self.local_yesterday:
            qd = now() - timedelta(1)
            field_count = 3
        elif query in self.local_thismonth:
            qd = now()
            field_count = 2
        else:
            m = self.daysago_pat.search(query)
            if m is not None:
                num = query[:-len(m.group(1))]
                try:
                    qd = now() - timedelta(int(num))
                except:
                    raise ParseException(query, len(query), 'Number conversion error')
                field_count = 3
            else:
                try:
                    qd = parse_date(query, as_utc=False)
                except:
                    raise ParseException(query, len(query), 'Date conversion error')
                if '-' in query:
                    field_count = query.count('-') + 1
                else:
                    field_count = query.count('/') + 1

        for v, book_ids in field_iter():
            if isinstance(v, (str, unicode)):
                v = parse_date(v)
            if v is not None and relop(v, qd, field_count):
                matches |= book_ids

        return matches
# }}}

class NumericSearch(object): # {{{

    def __init__(self):
        self.operators = {
            '=':( 1, lambda r, q: r == q ),
            '>':( 1, lambda r, q: r is not None and r > q ),
            '<':( 1, lambda r, q: r is not None and r < q ),
            '!=':( 2, lambda r, q: r != q ),
            '>=':( 2, lambda r, q: r is not None and r >= q ),
            '<=':( 2, lambda r, q: r is not None and r <= q )
        }

    def __call__(self, query, field_iter, location, datatype, candidates, is_many=False):
        matches = set()
        if not query:
            return matches

        q = ''
        cast = adjust = lambda x: x
        dt = datatype

        if is_many and query in {'true', 'false'}:
            valcheck = lambda x: True
            if datatype == 'rating':
                valcheck = lambda x: x is not None and x > 0
            found = set()
            for val, book_ids in field_iter():
                if valcheck(val):
                    found |= book_ids
            return found if query == 'true' else candidates - found

        if query == 'false':
            if location == 'cover':
                relop = lambda x,y: not bool(x)
            else:
                relop = lambda x,y: x is None
        elif query == 'true':
            if location == 'cover':
                relop = lambda x,y: bool(x)
            else:
                relop = lambda x,y: x is not None
        else:
            relop = None
            for k, op in self.operators.iteritems():
                if query.startswith(k):
                    p, relop = op
                    query = query[p:]
            if relop is None:
                p, relop = self.operators['=']

            cast = int
            if  dt == 'rating':
                cast = lambda x: 0 if x is None else int(x)
                adjust = lambda x: x/2
            elif dt in ('float', 'composite'):
                cast = float

            mult = 1.0
            if len(query) > 1:
                mult = query[-1].lower()
                mult = {'k': 1024.,'m': 1024.**2, 'g': 1024.**3}.get(mult, 1.0)
                if mult != 1.0:
                    query = query[:-1]
            else:
                mult = 1.0

            try:
                q = cast(query) * mult
            except:
                raise ParseException(query, len(query),
                                     'Non-numeric value in query: %r'%query)

        for val, book_ids in field_iter():
            if val is None:
                continue
            try:
                v = cast(val)
            except:
                v = None
            if v:
                v = adjust(v)
            if relop(v, q):
                matches |= book_ids
        return matches

# }}}

class BooleanSearch(object): # {{{

    def __init__(self):
        self.local_no        = icu_lower(_('no'))
        self.local_yes       = icu_lower(_('yes'))
        self.local_unchecked = icu_lower(_('unchecked'))
        self.local_checked   = icu_lower(_('checked'))
        self.local_empty     = icu_lower(_('empty'))
        self.local_blank     = icu_lower(_('blank'))
        self.local_bool_values = {
            self.local_no, self.local_unchecked, '_no', 'false', 'no',
            self.local_yes, self.local_checked, '_yes', 'true', 'yes',
            self.local_empty, self.local_blank, '_empty', 'empty'}

    def __call__(self, query, field_iter, bools_are_tristate):
        matches = set()
        if query not in self.local_bool_values:
            raise ParseException(_('Invalid boolean query "{0}"').format(query))
        for val, book_ids in field_iter():
            val = force_to_bool(val)
            if not bools_are_tristate:
                if val is None or not val: # item is None or set to false
                    if query in { self.local_no, self.local_unchecked, 'no', '_no', 'false' }:
                        matches |= book_ids
                else: # item is explicitly set to true
                    if query in { self.local_yes, self.local_checked, 'yes', '_yes', 'true' }:
                        matches |= book_ids
            else:
                if val is None:
                    if query in { self.local_empty, self.local_blank, 'empty', '_empty', 'false' }:
                        matches |= book_ids
                elif not val: # is not None and false
                    if query in { self.local_no, self.local_unchecked, 'no', '_no', 'true' }:
                        matches |= book_ids
                else: # item is not None and true
                    if query in { self.local_yes, self.local_checked, 'yes', '_yes', 'true' }:
                        matches |= book_ids
        return matches

# }}}

class KeyPairSearch(object): # {{{

    def __call__(self, query, field_iter, candidates, use_primary_find):
        matches = set()
        if ':' in query:
            q = [q.strip() for q in query.split(':')]
            if len(q) != 2:
                raise ParseException(query, len(query),
                        'Invalid query format for colon-separated search')
            keyq, valq = q
            keyq_mkind, keyq = _matchkind(keyq)
            valq_mkind, valq = _matchkind(valq)
        else:
            keyq = keyq_mkind = ''
            valq_mkind, valq = _matchkind(query)
            keyq_mkind

        if valq in {'true', 'false'}:
            found = set()
            if keyq:
                for val, book_ids in field_iter():
                    if val and val.get(keyq, False):
                        found |= book_ids
            else:
                for val, book_ids in field_iter():
                    if val:
                        found |= book_ids
            return found if valq == 'true' else candidates - found

        for m, book_ids in field_iter():
            for key, val in m.iteritems():
                if (keyq and not _match(keyq, (key,), keyq_mkind,
                                        use_primary_find_in_search=use_primary_find)):
                    continue
                if (valq and not _match(valq, (val,), valq_mkind,
                                        use_primary_find_in_search=use_primary_find)):
                    continue
                matches |= book_ids
                break

        return matches

# }}}

class Parser(SearchQueryParser):

    def __init__(self, dbcache, all_book_ids, gst, date_search, num_search,
                 bool_search, keypair_search, limit_search_columns, limit_search_columns_to,
                 locations):
        self.dbcache, self.all_book_ids = dbcache, all_book_ids
        self.all_search_locations = frozenset(locations)
        self.grouped_search_terms = gst
        self.date_search, self.num_search = date_search, num_search
        self.bool_search, self.keypair_search = bool_search, keypair_search
        self.limit_search_columns, self.limit_search_columns_to = (
            limit_search_columns, limit_search_columns_to)
        super(Parser, self).__init__(locations, optimize=True)

    @property
    def field_metadata(self):
        return self.dbcache.field_metadata

    def universal_set(self):
        return self.all_book_ids

    def field_iter(self, name, candidates):
        get_metadata = partial(self.dbcache._get_metadata, get_user_categories=False)
        return self.dbcache.fields[name].iter_searchable_values(get_metadata,
                                                                candidates)

    def get_matches(self, location, query, candidates=None,
                    allow_recursion=True):
        # If candidates is not None, it must not be modified. Changing its
        # value will break query optimization in the search parser
        matches = set()

        if candidates is None:
            candidates = self.all_book_ids
        if not candidates or not query or not query.strip():
            return matches
        if location not in self.all_search_locations:
            return matches

        if (len(location) > 2 and location.startswith('@') and
                    location[1:] in self.grouped_search_terms):
            location = location[1:]

        # get metadata key associated with the search term. Eliminates
        # dealing with plurals and other aliases
        original_location = location
        location = self.field_metadata.search_term_to_field_key(
            icu_lower(location.strip()))
        # grouped search terms
        if isinstance(location, list):
            if allow_recursion:
                if query.lower() == 'false':
                    invert = True
                    query = 'true'
                else:
                    invert = False
                for loc in location:
                    c = candidates.copy()
                    m = self.get_matches(loc, query,
                            candidates=c, allow_recursion=False)
                    matches |= m
                    c -= m
                    if len(c) == 0:
                        break
                if invert:
                    matches = self.all_book_ids - matches
                return matches
            raise ParseException(query, len(query), 'Recursive query group detected')

        # If the user has asked to restrict searching over all field, apply
        # that restriction
        if (location == 'all' and self.limit_search_columns and
            self.limit_search_columns_to):
            terms = set()
            for l in self.limit_search_columns_to:
                l = icu_lower(l.strip())
                if l and l != 'all' and l in self.all_search_locations:
                    terms.add(l)
            if terms:
                c = candidates.copy()
                for l in terms:
                    try:
                        m = self.get_matches(l, query,
                            candidates=c, allow_recursion=allow_recursion)
                        matches |= m
                        c -= m
                        if len(c) == 0:
                            break
                    except:
                        pass
                return matches

        if location in self.field_metadata:
            fm = self.field_metadata[location]
            dt = fm['datatype']

            # take care of dates special case
            if (dt == 'datetime' or (
                dt == 'composite' and
                fm['display'].get('composite_sort', '') == 'date')):
                if location == 'date':
                    location = 'timestamp'
                return self.date_search(
                    icu_lower(query), partial(self.field_iter, location, candidates))

            # take care of numbers special case
            if (dt in ('rating', 'int', 'float') or
                    (dt == 'composite' and
                     fm['display'].get('composite_sort', '') == 'number')):
                field = self.dbcache.fields[location]
                return self.num_search(
                    icu_lower(query), partial(self.field_iter, location, candidates),
                    location, dt, candidates, is_many=field.is_many)

            # take care of the 'count' operator for is_multiples
            if (fm['is_multiple'] and
                len(query) > 1 and query[0] == '#' and query[1] in '=<>!'):
                return self.num_search(icu_lower(query[1:]), partial(
                        self.dbcache.fields[location].iter_counts, candidates),
                    location, dt, candidates)

            # take care of boolean special case
            if dt == 'bool':
                return self.bool_search(icu_lower(query),
                                partial(self.field_iter, location, candidates),
                                self.dbcache.pref('bools_are_tristate'))

            # special case: colon-separated fields such as identifiers. isbn
            # is a special case within the case
            if fm.get('is_csp', False):
                field_iter = partial(self.field_iter, location, candidates)
                upf = prefs['use_primary_find_in_search']
                if location == 'identifiers' and original_location == 'isbn':
                    return self.keypair_search('=isbn:'+query, field_iter,
                                        candidates, upf)
                return self.keypair_search(query, field_iter, candidates, upf)

        return matches


class Search(object):

    def __init__(self, all_search_locations):
        self.all_search_locations = all_search_locations
        self.date_search = DateSearch()
        self.num_search = NumericSearch()
        self.bool_search = BooleanSearch()
        self.keypair_search = KeyPairSearch()

    def change_locations(self, newlocs):
        self.all_search_locations = newlocs

    def __call__(self, dbcache, query, search_restriction):
        '''
        Return the set of ids of all records that match the specified
        query and restriction
        '''
        q = ''
        if not query or not query.strip():
            q = search_restriction
        else:
            q = query
            if search_restriction:
                q = u'(%s) and (%s)' % (search_restriction, query)

        all_book_ids = dbcache.all_book_ids(type=set)
        if not q:
            return all_book_ids

        # We construct a new parser instance per search as pyparsing is not
        # thread safe. On my desktop, constructing a SearchQueryParser instance
        # takes 0.000975 seconds and restoring it from a pickle takes
        # 0.000974 seconds.
        sqp = Parser(
            dbcache, all_book_ids, dbcache.pref('grouped_search_terms'),
            self.date_search, self.num_search, self.bool_search,
            self.keypair_search,
            prefs[ 'limit_search_columns' ],
            prefs[ 'limit_search_columns_to' ], self.all_search_locations)
        try:
            ret = sqp.parse(query)
        finally:
            sqp.dbcache = None
        return ret

