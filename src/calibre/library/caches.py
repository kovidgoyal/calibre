#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, itertools, time, traceback
from itertools import repeat, izip, imap
from datetime import timedelta
from threading import Thread

from calibre.utils.config import tweaks, prefs
from calibre.utils.date import parse_date, now, UNDEFINED_DATE, clean_date_for_sort
from calibre.utils.search_query_parser import SearchQueryParser
from calibre.utils.pyparsing import ParseException
from calibre.utils.localization import (canonicalize_lang, lang_map, get_udc)
from calibre.ebooks.metadata import title_sort, author_to_author_sort
from calibre.ebooks.metadata.opf2 import metadata_to_opf
from calibre import prints
from calibre.utils.icu import primary_find

class MetadataBackup(Thread): # {{{
    '''
    Continuously backup changed metadata into OPF files
    in the book directory. This class runs in its own
    thread and makes sure that the actual file write happens in the
    GUI thread to prevent Windows' file locking from causing problems.
    '''

    def __init__(self, db):
        Thread.__init__(self)
        self.daemon = True
        self.db = db
        self.keep_running = True
        from calibre.gui2 import FunctionDispatcher
        self.do_write = FunctionDispatcher(self.write)
        self.get_metadata_for_dump = FunctionDispatcher(db.get_metadata_for_dump)
        self.clear_dirtied = FunctionDispatcher(db.clear_dirtied)
        self.set_dirtied = FunctionDispatcher(db.dirtied)

    def stop(self):
        self.keep_running = False

    def break_cycles(self):
        # Break cycles so that this object doesn't hold references to db
        self.do_write = self.get_metadata_for_dump = self.clear_dirtied = \
            self.set_dirtied = self.db = None

    def run(self):
        while self.keep_running:
            try:
                time.sleep(2) # Limit to one book per two seconds
                (id_, sequence) = self.db.get_a_dirtied_book()
                if id_ is None:
                    continue
                # print 'writer thread', id_, sequence
            except:
                # Happens during interpreter shutdown
                break
            if not self.keep_running:
                break

            try:
                path, mi, sequence = self.get_metadata_for_dump(id_)
            except:
                prints('Failed to get backup metadata for id:', id_, 'once')
                traceback.print_exc()
                time.sleep(2)
                try:
                    path, mi, sequence = self.get_metadata_for_dump(id_)
                except:
                    prints('Failed to get backup metadata for id:', id_, 'again, giving up')
                    traceback.print_exc()
                    continue

            if mi is None:
                self.clear_dirtied(id_, sequence)
                continue
            if not self.keep_running:
                break

            # Give the GUI thread a chance to do something. Python threads don't
            # have priorities, so this thread would naturally keep the processor
            # until some scheduling event happens. The sleep makes such an event
            time.sleep(0.1)
            try:
                raw = metadata_to_opf(mi)
            except:
                prints('Failed to convert to opf for id:', id_)
                traceback.print_exc()
                continue

            if not self.keep_running:
                break

            time.sleep(0.1) # Give the GUI thread a chance to do something
            try:
                self.do_write(path, raw)
            except:
                prints('Failed to write backup metadata for id:', id_, 'once')
                time.sleep(2)
                try:
                    self.do_write(path, raw)
                except:
                    prints('Failed to write backup metadata for id:', id_,
                            'again, giving up')
                    continue

            self.clear_dirtied(id_, sequence)
        self.break_cycles()

    def write(self, path, raw):
        with lopen(path, 'wb') as f:
            f.write(raw)


# }}}


### Global utility function for get_match here and in gui2/library.py
# This is a global for performance
pref_use_primary_find_in_search = False

def set_use_primary_find_in_search(toWhat):
    global pref_use_primary_find_in_search
    pref_use_primary_find_in_search = toWhat

CONTAINS_MATCH = 0
EQUALS_MATCH   = 1
REGEXP_MATCH   = 2
def _match(query, value, matchkind):
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
                return re.search(query, t, re.I|re.UNICODE)
            elif matchkind == CONTAINS_MATCH:
                if pref_use_primary_find_in_search:
                    return primary_find(query, t)[0] != -1
                else:
                    return query in t
        except re.error:
            pass
    return False

def force_to_bool(val):
    if isinstance(val, (str, unicode)):
        try:
            val = icu_lower(val)
            if not val:
                val = None
            elif val in [_('yes'), _('checked'), 'true']:
                val = True
            elif val in [_('no'), _('unchecked'), 'false']:
                val = False
            else:
                val = bool(int(val))
        except:
            val = None
    return val

class CacheRow(list): # {{{

    def __init__(self, db, composites, val, series_col, series_sort_col):
        self.db = db
        self._composites = composites
        list.__init__(self, val)
        self._must_do = len(composites) > 0
        self._series_col = series_col
        self._series_sort_col = series_sort_col
        self._series_sort = None

    def __getitem__(self, col):
        if self._must_do:
            is_comp = False
            if isinstance(col, slice):
                start = 0 if col.start is None else col.start
                step = 1 if col.stop is None else col.stop
                for c in range(start, col.stop, step):
                    if c in self._composites:
                        is_comp = True
                        break
            elif col in self._composites:
                is_comp = True
            if is_comp:
                id_ = list.__getitem__(self, 0)
                self._must_do = False
                mi = self.db.get_metadata(id_, index_is_id=True,
                                          get_user_categories=False)
                for c in self._composites:
                    self[c] =  mi.get(self._composites[c])
        if col == self._series_sort_col and self._series_sort is None:
            if self[self._series_col]:
                self._series_sort = title_sort(self[self._series_col])
                self[self._series_sort_col] = self._series_sort
            else:
                self._series_sort = ''
                self[self._series_sort_col] = ''
        return list.__getitem__(self, col)

    def __getslice__(self, i, j):
        return self.__getitem__(slice(i, j))

    def refresh_composites(self):
        for c in self._composites:
            self[c] =  None
        self._must_do = True

# }}}

class ResultCache(SearchQueryParser): # {{{

    '''
    Stores sorted and filtered metadata in memory.
    '''
    def __init__(self, FIELD_MAP, field_metadata, db_prefs=None):
        self.FIELD_MAP = FIELD_MAP
        self.db_prefs = db_prefs
        self.composites = {}
        self.udc = get_udc()
        for key in field_metadata:
            if field_metadata[key]['datatype'] == 'composite':
                self.composites[field_metadata[key]['rec_index']] = key
        self.series_col = field_metadata['series']['rec_index']
        self.series_sort_col = field_metadata['series_sort']['rec_index']
        self._data = []
        self._map = self._map_filtered = []
        self.first_sort = True
        self.search_restriction = ''
        self.search_restriction_book_count = 0
        self.marked_ids_dict = {}
        self.field_metadata = field_metadata
        self.all_search_locations = field_metadata.get_search_terms()
        SearchQueryParser.__init__(self, self.all_search_locations, optimize=True)
        self.build_date_relop_dict()
        self.build_numeric_relop_dict()
        # Do this here so the var get updated when a library changes
        global pref_use_primary_find_in_search
        pref_use_primary_find_in_search = prefs['use_primary_find_in_search']

    def break_cycles(self):
        self._data = self.field_metadata = self.FIELD_MAP = \
            self.numeric_search_relops = self.date_search_relops = \
            self.db_prefs = self.all_search_locations = None
        self.sqp_change_locations([])


    def __getitem__(self, row):
        return self._data[self._map_filtered[row]]

    def __len__(self):
        return len(self._map_filtered)

    def __iter__(self):
        for id in self._map_filtered:
            yield self._data[id]

    def iterall(self):
        for x in self._data:
            if x is not None:
                yield x

    def iterallids(self):
        idx = self.FIELD_MAP['id']
        for x in self.iterall():
            yield x[idx]

    # Search functions {{{

    def universal_set(self):
        return set([i[0] for i in self._data if i is not None])

    def change_search_locations(self, locations):
        self.sqp_change_locations(locations)
        self.all_search_locations = locations

    def build_date_relop_dict(self):
        '''
        Because the database dates have time in them, we can't use direct
        comparisons even when field_count == 3. The query has time = 0, but
        the database object has time == something. As such, a complete compare
        will almost never be correct.
        '''
        def relop_eq(db, query, field_count):
            if db.year == query.year:
                if field_count == 1:
                    return True
                if db.month == query.month:
                    if field_count == 2:
                        return True
                    return db.day == query.day
            return False

        def relop_gt(db, query, field_count):
            if db.year > query.year:
                return True
            if field_count > 1 and db.year == query.year:
                if db.month > query.month:
                    return True
                return field_count == 3 and db.month == query.month and db.day > query.day
            return False

        def relop_lt(db, query, field_count):
            if db.year < query.year:
                return True
            if field_count > 1 and db.year == query.year:
                if db.month < query.month:
                    return True
                return field_count == 3 and db.month == query.month and db.day < query.day
            return False

        def relop_ne(db, query, field_count):
            return not relop_eq(db, query, field_count)

        def relop_ge(db, query, field_count):
            return not relop_lt(db, query, field_count)

        def relop_le(db, query, field_count):
            return not relop_gt(db, query, field_count)

        self.date_search_relops = {
                            '=' :[1, relop_eq],
                            '>' :[1, relop_gt],
                            '<' :[1, relop_lt],
                            '!=':[2, relop_ne],
                            '>=':[2, relop_ge],
                            '<=':[2, relop_le]
                        }

    def get_dates_matches(self, location, query, candidates):
        matches = set([])
        if len(query) < 2:
            return matches

        if location == 'date':
            location = 'timestamp'
        loc = self.field_metadata[location]['rec_index']

        if query == 'false':
            for id_ in candidates:
                item = self._data[id_]
                if item is None: continue
                v = item[loc]
                if isinstance(v, (str, unicode)):
                    v = parse_date(v)
                if v is None or v <= UNDEFINED_DATE:
                    matches.add(item[0])
            return matches
        if query == 'true':
            for id_ in candidates:
                item = self._data[id_]
                if item is None: continue
                v = item[loc]
                if isinstance(v, (str, unicode)):
                    v = parse_date(v)
                if v is not None and v > UNDEFINED_DATE:
                    matches.add(item[0])
            return matches

        relop = None
        for k in self.date_search_relops.keys():
            if query.startswith(k):
                (p, relop) = self.date_search_relops[k]
                query = query[p:]
        if relop is None:
                (p, relop) = self.date_search_relops['=']

        if query == _('today'):
            qd = now()
            field_count = 3
        elif query == _('yesterday'):
            qd = now() - timedelta(1)
            field_count = 3
        elif query == _('thismonth'):
            qd = now()
            field_count = 2
        elif query.endswith(_('daysago')):
            num = query[0:-len(_('daysago'))]
            try:
                qd = now() - timedelta(int(num))
            except:
                raise ParseException(query, len(query), 'Number conversion error', self)
            field_count = 3
        else:
            try:
                qd = parse_date(query, as_utc=False)
            except:
                raise ParseException(query, len(query), 'Date conversion error', self)
            if '-' in query:
                field_count = query.count('-') + 1
            else:
                field_count = query.count('/') + 1
        for id_ in candidates:
            item = self._data[id_]
            if item is None or item[loc] is None: continue
            v = item[loc]
            if isinstance(v, (str, unicode)):
                v = parse_date(v)
            if relop(v, qd, field_count):
                matches.add(item[0])
        return matches

    def build_numeric_relop_dict(self):
        self.numeric_search_relops = {
                        '=':[1, lambda r, q: r == q],
                        '>':[1, lambda r, q: r is not None and r > q],
                        '<':[1, lambda r, q: r is not None and r < q],
                        '!=':[2, lambda r, q: r != q],
                        '>=':[2, lambda r, q: r is not None and r >= q],
                        '<=':[2, lambda r, q: r is not None and r <= q]
                    }

    def get_numeric_matches(self, location, query, candidates, val_func = None):
        matches = set([])
        if len(query) == 0:
            return matches

        if val_func is None:
            loc = self.field_metadata[location]['rec_index']
            val_func = lambda item, loc=loc: item[loc]
        q = ''
        cast = adjust = lambda x: x
        dt = self.field_metadata[location]['datatype']

        if query == 'false':
            if dt == 'rating' or location == 'cover':
                relop = lambda x,y: not bool(x)
            else:
                relop = lambda x,y: x is None
        elif query == 'true':
            if dt == 'rating' or location == 'cover':
                relop = lambda x,y: bool(x)
            else:
                relop = lambda x,y: x is not None
        else:
            relop = None
            for k in self.numeric_search_relops.keys():
                if query.startswith(k):
                    (p, relop) = self.numeric_search_relops[k]
                    query = query[p:]
            if relop is None:
                    (p, relop) = self.numeric_search_relops['=']

            if dt == 'int':
                cast = lambda x: int (x)
            elif  dt == 'rating':
                cast = lambda x: 0 if x is None else int (x)
                adjust = lambda x: x/2
            elif dt in ('float', 'composite'):
                cast = lambda x : float (x)
            else: # count operation
                cast = (lambda x: int (x))

            if len(query) > 1:
                mult = query[-1:].lower()
                mult = {'k':1024.,'m': 1024.**2, 'g': 1024.**3}.get(mult, 1.0)
                if mult != 1.0:
                    query = query[:-1]
            else:
                mult = 1.0
            try:
                q = cast(query) * mult
            except:
                raise ParseException(query, len(query),
                                     'Non-numeric value in query', self)

        for id_ in candidates:
            item = self._data[id_]
            if item is None:
                continue
            try:
                v = cast(val_func(item))
            except:
                v = None
            if v:
                v = adjust(v)
            if relop(v, q):
                matches.add(item[0])
        return matches

    def get_user_category_matches(self, location, query, candidates):
        matches = set([])
        if self.db_prefs is None or len(query) < 2:
            return  matches
        user_cats = self.db_prefs.get('user_categories', [])
        c = set(candidates)

        if query.startswith('.'):
            check_subcats = True
            query = query[1:]
        else:
            check_subcats = False

        for key in user_cats:
            if key == location or (check_subcats and key.startswith(location + '.')):
                for (item, category, ign) in user_cats[key]:
                    s = self.get_matches(category, '=' + item, candidates=c)
                    c -= s
                    matches |= s
        if query == 'false':
            return candidates - matches
        return matches

    def get_keypair_matches(self, location, query, candidates):
        matches = set([])
        if query.find(':') >= 0:
            q = [q.strip() for q in query.split(':')]
            if len(q) != 2:
                raise ParseException(query, len(query),
                        'Invalid query format for colon-separated search', self)
            (keyq, valq) = q
            keyq_mkind, keyq = self._matchkind(keyq)
            valq_mkind, valq = self._matchkind(valq)
        else:
            keyq = keyq_mkind = ''
            valq_mkind, valq = self._matchkind(query)

        loc = self.field_metadata[location]['rec_index']
        split_char = self.field_metadata[location]['is_multiple'].get(
                'cache_to_list', ',')
        for id_ in candidates:
            item = self._data[id_]
            if item is None:
                continue

            if item[loc] is None:
                if valq == 'false':
                    matches.add(id_)
                continue

            pairs = [p.strip() for p in item[loc].split(split_char)]
            for pair in pairs:
                parts = pair.split(':')
                if len(parts) != 2:
                    continue
                k = parts[:1]
                v = parts[1:]
                if keyq and not _match(keyq, k, keyq_mkind):
                    continue
                if valq:
                    if valq == 'true':
                        if not v:
                            continue
                    elif valq == 'false':
                        if v:
                            continue
                    elif not _match(valq, v, valq_mkind):
                        continue
                matches.add(id_)
        return matches

    def _matchkind(self, query):
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

    def get_bool_matches(self, location, query, candidates):
        bools_are_tristate = self.db_prefs.get('bools_are_tristate')
        loc = self.field_metadata[location]['rec_index']
        matches = set()
        query = icu_lower(query)
        if query not in (_('no'), _('unchecked'), '_no', 'false',
                         _('yes'), _('checked'), '_yes', 'true',
                         _('empty'), _('blank'), '_empty'):
            raise ParseException(_('Invalid boolean query "{0}"').format(query))
        for id_ in candidates:
            item = self._data[id_]
            if item is None:
                continue

            val = force_to_bool(item[loc])
            if not bools_are_tristate:
                if val is None or not val: # item is None or set to false
                    if query in [_('no'), _('unchecked'), '_no', 'false']:
                        matches.add(item[0])
                else: # item is explicitly set to true
                    if query in [_('yes'), _('checked'), '_yes', 'true']:
                        matches.add(item[0])
            else:
                if val is None:
                    if query in [_('empty'), _('blank'), '_empty', 'false']:
                        matches.add(item[0])
                elif not val: # is not None and false
                    if query in [_('no'), _('unchecked'), '_no', 'true']:
                        matches.add(item[0])
                else: # item is not None and true
                    if query in [_('yes'), _('checked'), '_yes', 'true']:
                        matches.add(item[0])
        return matches

    def get_matches(self, location, query, candidates=None,
            allow_recursion=True):
        matches = set([])
        if candidates is None:
            candidates = self.universal_set()
        if len(candidates) == 0:
            return matches
        if location not in self.all_search_locations:
            return matches

        if len(location) > 2 and location.startswith('@') and \
                    location[1:] in self.db_prefs['grouped_search_terms']:
            location = location[1:]

        if query and query.strip():
            # get metadata key associated with the search term. Eliminates
            # dealing with plurals and other aliases
            original_location = location
            location = self.field_metadata.search_term_to_field_key(icu_lower(location.strip()))
            # grouped search terms
            if isinstance(location, list):
                if allow_recursion:
                    if query.lower() == 'false':
                        invert = True
                        query = 'true'
                    else:
                        invert = False
                    for loc in location:
                        m = self.get_matches(loc, query,
                                candidates=candidates, allow_recursion=False)
                        matches |= m
                        candidates -= m
                    if invert:
                        matches = self.universal_set() - matches
                    return matches
                raise ParseException(query, len(query), 'Recursive query group detected', self)

            # apply the limit if appropriate
            if location == 'all' and prefs['limit_search_columns'] and \
                            prefs['limit_search_columns_to']:
                terms = set([])
                for l in prefs['limit_search_columns_to']:
                    l = icu_lower(l.strip())
                    if l and l != 'all' and l in self.all_search_locations:
                        terms.add(l)
                if terms:
                    for l in terms:
                        try:
                            m = self.get_matches(l, query,
                                candidates=candidates, allow_recursion=allow_recursion)
                            matches |= m
                            candidates -= m
                        except:
                            pass
                    return matches

            if location in self.field_metadata:
                fm = self.field_metadata[location]
                # take care of dates special case
                if fm['datatype'] == 'datetime' or \
                        (fm['datatype'] == 'composite' and
                         fm['display'].get('composite_sort', '') == 'date'):
                    return self.get_dates_matches(location, query.lower(), candidates)

                # take care of numbers special case
                if fm['datatype'] in ('rating', 'int', 'float') or \
                        (fm['datatype'] == 'composite' and
                         fm['display'].get('composite_sort', '') == 'number'):
                    return self.get_numeric_matches(location, query.lower(), candidates)

                if fm['datatype'] == 'bool':
                    return self.get_bool_matches(location, query, candidates)

                # take care of the 'count' operator for is_multiples
                if fm['is_multiple'] and \
                        len(query) > 1 and query.startswith('#') and \
                        query[1:1] in '=<>!':
                    vf = lambda item, loc=fm['rec_index'], \
                                ms=fm['is_multiple']['cache_to_list']:\
                            len(item[loc].split(ms)) if item[loc] is not None else 0
                    return self.get_numeric_matches(location, query[1:],
                                                    candidates, val_func=vf)

                # special case: colon-separated fields such as identifiers. isbn
                # is a special case within the case
                if fm.get('is_csp', False):
                    if location == 'identifiers' and original_location == 'isbn':
                        return self.get_keypair_matches('identifiers',
                                                   '=isbn:'+query, candidates)
                    return self.get_keypair_matches(location, query, candidates)

            # check for user categories
            if len(location) >= 2 and location.startswith('@'):
                return self.get_user_category_matches(location[1:], query.lower(),
                                                      candidates)
            # everything else, or 'all' matches
            matchkind, query = self._matchkind(query)

            if not isinstance(query, unicode):
                query = query.decode('utf-8')

            db_col = {}
            exclude_fields = [] # fields to not check when matching against text.
            col_datatype = []
            is_multiple_cols = {}
            for x in range(len(self.FIELD_MAP)):
                col_datatype.append('')
            for x in self.field_metadata:
                if x.startswith('@'):
                    continue
                if len(self.field_metadata[x]['search_terms']):
                    db_col[x] = self.field_metadata[x]['rec_index']
                    if self.field_metadata[x]['datatype'] not in \
                            ['composite', 'text', 'comments', 'series', 'enumeration']:
                        exclude_fields.append(db_col[x])
                    col_datatype[db_col[x]] = self.field_metadata[x]['datatype']
                    is_multiple_cols[db_col[x]] = \
                        self.field_metadata[x]['is_multiple'].get('cache_to_list', None)

            try:
                rating_query = int(query) * 2
            except:
                rating_query = None

            location = [location] if location != 'all' else list(db_col.keys())
            for i, loc in enumerate(location):
                location[i] = db_col[loc]

            for loc in location: # location is now an array of field indices
                if loc == db_col['authors']:
                    ### DB stores authors with commas changed to bars, so change query
                    if matchkind == REGEXP_MATCH:
                        q = query.replace(',', r'\|')
                    else:
                        q = query.replace(',', '|')
                elif loc == db_col['languages']:
                    q = canonicalize_lang(query)
                    if q is None:
                        lm = lang_map()
                        rm = {v.lower():k for k,v in lm.iteritems()}
                        q = rm.get(query, query)
                else:
                    q = query

                for id_ in candidates:
                    item = self._data[id_]
                    if item is None: continue

                    if not item[loc]:
                        if q == 'false' and matchkind == CONTAINS_MATCH:
                            matches.add(item[0])
                        continue     # item is empty. No possible matches below
                    if q == 'false'and matchkind == CONTAINS_MATCH:
                        # Field has something in it, so a false query does not match
                        continue

                    if q == 'true' and matchkind == CONTAINS_MATCH:
                        if isinstance(item[loc], basestring):
                            if item[loc].strip() == '':
                                continue
                        matches.add(item[0])
                        continue

                    if col_datatype[loc] == 'rating': # get here if 'all' query
                        if rating_query and rating_query == int(item[loc]):
                            matches.add(item[0])
                        continue

                    try: # a conversion below might fail
                        # relationals are not supported in 'all' queries
                        if col_datatype[loc] == 'float':
                            if float(query) == item[loc]:
                                matches.add(item[0])
                            continue
                        if col_datatype[loc] == 'int':
                            if int(query) == item[loc]:
                                matches.add(item[0])
                            continue
                    except:
                        # A conversion threw an exception. Because of the type,
                        # no further match is possible
                        continue

                    if loc not in exclude_fields: # time for text matching
                        if is_multiple_cols[loc] is not None:
                            vals = [v.strip() for v in item[loc].split(is_multiple_cols[loc])]
                        else:
                            vals = [item[loc]] ### make into list to make _match happy
                        if _match(q, vals, matchkind):
                            matches.add(item[0])
                            continue
        return matches

    def search(self, query, return_matches=False):
        ans = self.search_getting_ids(query, self.search_restriction,
                                      set_restriction_count=True)
        if return_matches:
            return ans
        self._map_filtered = ans

    def search_getting_ids(self, query, search_restriction,
                           set_restriction_count=False):
        q = ''
        if not query or not query.strip():
            q = search_restriction
        else:
            q = query
            if search_restriction:
                q = u'(%s) and (%s)' % (search_restriction, query)
        if not q:
            if set_restriction_count:
                self.search_restriction_book_count = len(self._map)
            return list(self._map)
        matches = self.parse(q)
        tmap = list(itertools.repeat(False, len(self._data)))
        for x in matches:
            tmap[x] = True
        rv = [x for x in self._map if tmap[x]]
        if set_restriction_count and q == search_restriction:
            self.search_restriction_book_count = len(rv)
        return rv

    def set_search_restriction(self, s):
        self.search_restriction = s

    def search_restriction_applied(self):
        return bool(self.search_restriction)

    def get_search_restriction_book_count(self):
        return self.search_restriction_book_count

    def set_marked_ids(self, id_dict):
        '''
        ids in id_dict are "marked". They can be searched for by
        using the search term ``marked:true``. Pass in an empty dictionary or
        set to clear marked ids.

        :param id_dict: Either a dictionary mapping ids to values or a set
        of ids. In the latter case, the value is set to 'true' for all ids. If
        a mapping is provided, then the search can be used to search for
        particular values: ``marked:value``
        '''
        if not hasattr(id_dict, 'items'):
            # Simple list. Make it a dict of string 'true'
            self.marked_ids_dict = dict.fromkeys(id_dict, u'true')
        else:
            # Ensure that all the items in the dict are text
            self.marked_ids_dict = dict(izip(id_dict.iterkeys(), imap(unicode,
                id_dict.itervalues())))

        # Set the values in the cache
        marked_col = self.FIELD_MAP['marked']
        for r in self.iterall():
            r[marked_col] = None

        for id_, val in self.marked_ids_dict.iteritems():
            try:
                self._data[id_][marked_col] = val
            except:
                pass

    # }}}

    def remove(self, id):
        try:
            self._data[id] = None
        except IndexError:
            # id is out of bounds, no point setting it to None anyway
            pass
        try:
            self._map.remove(id)
        except ValueError:
            pass
        try:
            self._map_filtered.remove(id)
        except ValueError:
            pass

    def set(self, row, col, val, row_is_id=False):
        id = row if row_is_id else self._map_filtered[row]
        self._data[id][col] = val

    def get(self, row, col, row_is_id=False):
        id = row if row_is_id else self._map_filtered[row]
        return self._data[id][col]

    def index(self, id, cache=False):
        x = self._map if cache else self._map_filtered
        return x.index(id)

    def row(self, id):
        return self.index(id)

    def has_id(self, id):
        try:
            return self._data[id] is not None
        except IndexError:
            pass
        return False

    def refresh_ids(self, db, ids):
        '''
        Refresh the data in the cache for books identified by ids.
        Returns a list of affected rows or None if the rows are filtered.
        '''
        for id in ids:
            try:
                self._data[id] = CacheRow(db, self.composites,
                        db.conn.get('SELECT * from meta2 WHERE id=?', (id,))[0],
                        self.series_col, self.series_sort_col)
                self._data[id].append(db.book_on_device_string(id))
                self._data[id].append(self.marked_ids_dict.get(id, None))
                self._data[id].append(None)
            except IndexError:
                return None
        try:
            return map(self.row, ids)
        except ValueError:
            pass
        return None

    def books_added(self, ids, db):
        if not ids:
            return
        self._data.extend(repeat(None, max(ids)-len(self._data)+2))
        for id in ids:
            self._data[id] = CacheRow(db, self.composites,
                        db.conn.get('SELECT * from meta2 WHERE id=?', (id,))[0],
                        self.series_col, self.series_sort_col)
            self._data[id].append(db.book_on_device_string(id))
            self._data[id].append(self.marked_ids_dict.get(id, None))
            self._data[id].append(None) # Series sort column
        self._map[0:0] = ids
        self._map_filtered[0:0] = ids

    def books_deleted(self, ids):
        for id in ids:
            self.remove(id)

    def count(self):
        return len(self._map)

    def refresh_ondevice(self, db):
        ondevice_col = self.FIELD_MAP['ondevice']
        for item in self._data:
            if item is not None:
                item[ondevice_col] = db.book_on_device_string(item[0])
                item.refresh_composites()

    def refresh(self, db, field=None, ascending=True):
        # reinitialize the template cache in case a composite column has changed
        db.initialize_template_cache()

        temp = db.conn.get('SELECT * FROM meta2')
        self._data = list(itertools.repeat(None, temp[-1][0]+2)) if temp else []
        for r in temp:
            self._data[r[0]] = CacheRow(db, self.composites, r,
                                        self.series_col, self.series_sort_col)
        for item in self._data:
            if item is not None:
                item.append(db.book_on_device_string(item[0]))
                # Temp mark and series_sort columns
                item.extend((None, None))

        marked_col = self.FIELD_MAP['marked']
        for id_,val in self.marked_ids_dict.iteritems():
            try:
                self._data[id_][marked_col] = val
            except:
                pass

        self._map = [i[0] for i in self._data if i is not None]
        if field is not None:
            self.sort(field, ascending)
        self._map_filtered = list(self._map)
        if self.search_restriction:
            self.search('', return_matches=False)

    # Sorting functions {{{

    def sanitize_sort_field_name(self, field):
        field = self.field_metadata.search_term_to_field_key(field.lower().strip())
        # translate some fields to their hidden equivalent
        if field == 'title': field = 'sort'
        elif field == 'authors': field = 'author_sort'
        return field

    def sort(self, field, ascending, subsort=False):
        self.multisort([(field, ascending)])

    def multisort(self, fields=[], subsort=False, only_ids=None):
        '''
        fields is a list of 2-tuple, each tuple is of the form
        (field_name, is_ascending)

        If only_ids is a list of ids, this function will sort that list instead
        of the internal mapping of ids.
        '''
        fields = [(self.sanitize_sort_field_name(x), bool(y)) for x, y in fields]
        keys = self.field_metadata.sortable_field_keys()
        fields = [x for x in fields if x[0] in keys]
        if subsort and 'sort' not in [x[0] for x in fields]:
            fields += [('sort', True)]
        if not fields:
            fields = [('timestamp', False)]

        keyg = SortKeyGenerator(fields, self.field_metadata, self._data, self.db_prefs)
        if only_ids is None:
            self._map.sort(key=keyg)

            tmap = list(itertools.repeat(False, len(self._data)))
            for x in self._map_filtered:
                tmap[x] = True
            self._map_filtered = [x for x in self._map if tmap[x]]
        else:
            only_ids.sort(key=keyg)

class SortKey(object):

    def __init__(self, orders, values):
        self.orders, self.values = orders, values

    def __cmp__(self, other):
        for i, ascending in enumerate(self.orders):
            ans = cmp(self.values[i], other.values[i])
            if ans != 0:
                return ans * ascending
        return 0

class SortKeyGenerator(object):

    def __init__(self, fields, field_metadata, data, db_prefs):
        from calibre.utils.icu import sort_key
        self.field_metadata = field_metadata
        self.db_prefs = db_prefs
        self.orders = [1 if x[1] else -1 for x in fields]
        self.entries = [(x[0], field_metadata[x[0]]) for x in fields]
        self.library_order = tweaks['title_series_sorting'] == 'library_order'
        self.data = data
        self.string_sort_key = sort_key

    def __call__(self, record):
        values = tuple(self.itervals(self.data[record]))
        return SortKey(self.orders, values)

    def itervals(self, record):
        for name, fm in self.entries:
            dt = fm['datatype']
            val = record[fm['rec_index']]
            if dt == 'composite':
                sb = fm['display'].get('composite_sort', 'text')
                if sb == 'date':
                    try:
                        val = parse_date(val)
                    except:
                        val = UNDEFINED_DATE
                    dt = 'datetime'
                elif sb == 'number':
                    try:
                        val = val.replace(',', '').strip()
                        p = 1
                        for i, candidate in enumerate(
                                    (' B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB')):
                            if val.endswith(candidate):
                                p = 1024**(i)
                                val = val[:-len(candidate)].strip()
                                break
                        val = float(val) * p
                    except:
                        val = 0.0
                    dt = 'float'
                elif sb == 'bool':
                    val = force_to_bool(val)
                    dt = 'bool'

            if dt == 'datetime':
                if val is None:
                    val = UNDEFINED_DATE
                if tweaks['sort_dates_using_visible_fields']:
                    format = None
                    if name == 'timestamp':
                        format = tweaks['gui_timestamp_display_format']
                    elif name == 'pubdate':
                        format = tweaks['gui_pubdate_display_format']
                    elif name == 'last_modified':
                        format = tweaks['gui_last_modified_display_format']
                    elif fm['is_custom']:
                        format = fm['display'].get('date_format', None)
                    val = clean_date_for_sort(val, format)
            elif dt == 'series':
                if val is None:
                    val = ('', 1)
                else:
                    if self.library_order:
                        val = title_sort(val)
                    sidx_fm = self.field_metadata[name + '_index']
                    sidx = record[sidx_fm['rec_index']]
                    val = (self.string_sort_key(val), sidx)

            elif dt in ('text', 'comments', 'composite', 'enumeration'):
                if val:
                    if fm['is_multiple']:
                        jv = fm['is_multiple']['list_to_ui']
                        sv = fm['is_multiple']['cache_to_list']
                        if '&' in jv:
                            val = jv.join(
                                [author_to_author_sort(v) for v in val.split(sv)])
                        else:
                            val = jv.join(sorted(val.split(sv),
                                              key=self.string_sort_key))
                val = self.string_sort_key(val)

            elif dt == 'bool':
                if not self.db_prefs.get('bools_are_tristate'):
                    val = {True: 1, False: 2, None: 2}.get(val, 2)
                else:
                    val = {True: 1, False: 2, None: 3}.get(val, 3)

            yield val

    # }}}

# }}}

