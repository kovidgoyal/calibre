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
from calibre.utils.search_query_parser import SearchQueryParser, ParseException

# TODO: Thread safety of saved searches

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

class Parser(SearchQueryParser):

    def __init__(self, dbcache, all_book_ids, gst, date_search,
                 limit_search_columns, limit_search_columns_to, locations):
        self.dbcache, self.all_book_ids = dbcache, all_book_ids
        self.all_search_locations = frozenset(locations)
        self.grouped_search_terms = gst
        self.date_search = date_search
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
        # original_location = location
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
            # take care of dates special case
            if (fm['datatype'] == 'datetime' or
                    (fm['datatype'] == 'composite' and
                     fm['display'].get('composite_sort', '') == 'date')):
                if location == 'date':
                    location = 'timestamp'
                return self.date_search(
                    icu_lower(query), partial(self.field_iter, location, candidates))

        return matches


class Search(object):

    def __init__(self, all_search_locations):
        self.all_search_locations = all_search_locations
        self.date_search = DateSearch()

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
            self.date_search, prefs[ 'limit_search_columns' ],
            prefs[ 'limit_search_columns_to' ], self.all_search_locations)
        try:
            ret = sqp.parse(query)
        finally:
            sqp.dbcache = None
        return ret

