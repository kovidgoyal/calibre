#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import regex, weakref, operator
from functools import partial
from datetime import timedelta
from collections import deque, OrderedDict

from calibre.constants import preferred_encoding, DEBUG
from calibre.db.utils import force_to_bool
from calibre.utils.config_base import prefs
from calibre.utils.date import parse_date, UNDEFINED_DATE, now, dt_as_local
from calibre.utils.icu import primary_no_punc_contains, primary_contains, sort_key
from calibre.utils.localization import lang_map, canonicalize_lang
from calibre.utils.search_query_parser import SearchQueryParser, ParseException
from polyglot.builtins import iteritems, string_or_bytes

CONTAINS_MATCH = 0
EQUALS_MATCH   = 1
REGEXP_MATCH   = 2
ACCENT_MATCH   = 3

# Utils {{{


def _matchkind(query, case_sensitive=False):
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
        elif query.startswith('^'):
            matchkind = ACCENT_MATCH
            query = query[1:]

    if not case_sensitive and matchkind != REGEXP_MATCH:
        # leave case in regexps because it can be significant e.g. \S \W \D
        query = icu_lower(query)
    return matchkind, query


def _match(query, value, matchkind, use_primary_find_in_search=True, case_sensitive=False):
    if query.startswith('..'):
        query = query[1:]
        sq = query[1:]
        internal_match_ok = True
    else:
        internal_match_ok = False
    for t in value:
        try:  # ignore regexp exceptions, required because search-ahead tries before typing is finished
            if not case_sensitive:
                t = icu_lower(t)
            if (matchkind == EQUALS_MATCH):
                if internal_match_ok:
                    if query == t:
                        return True
                    return sq in [c.strip() for c in t.split('.') if c.strip()]
                elif query[0] == '.':
                    if t.startswith(query[1:]):
                        ql = len(query) - 1
                        if (len(t) == ql) or (t[ql:ql+1] == '.'):
                            return True
                elif query == t:
                    return True
            elif matchkind == REGEXP_MATCH:
                flags = regex.UNICODE | regex.VERSION1 | regex.FULLCASE | (0 if case_sensitive else regex.IGNORECASE)
                if regex.search(query, t, flags) is not None:
                    return True
            elif matchkind == ACCENT_MATCH:
                if primary_contains(query, t):
                    return True
            elif matchkind == CONTAINS_MATCH:
                if not case_sensitive and use_primary_find_in_search:
                    if primary_no_punc_contains(query, t):
                        return True
                elif query in t:
                    return True
        except regex.error:
            pass
    return False
# }}}


class DateSearch:  # {{{

    def __init__(self):
        self.operators = OrderedDict((
            ('!=', self.ne),
            ('>=', self.ge),
            ('<=', self.le),
            ('=', self.eq),
            ('>', self.gt),
            ('<', self.lt),
        ))
        self.local_today         = {'_today', 'today', icu_lower(_('today'))}
        self.local_yesterday     = {'_yesterday', 'yesterday', icu_lower(_('yesterday'))}
        self.local_thismonth     = {'_thismonth', 'thismonth', icu_lower(_('thismonth'))}
        self.daysago_pat = regex.compile(r'(%s|daysago|_daysago)$'%_('daysago'), flags=regex.UNICODE | regex.VERSION1)

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
                if isinstance(v, (bytes, str)):
                    if isinstance(v, bytes):
                        v = v.decode(preferred_encoding, 'replace')
                    v = parse_date(v)
                if v is None or v <= UNDEFINED_DATE:
                    matches |= book_ids
            return matches

        if query == 'true':
            for v, book_ids in field_iter():
                if isinstance(v, (bytes, str)):
                    if isinstance(v, bytes):
                        v = v.decode(preferred_encoding, 'replace')
                    v = parse_date(v)
                if v is not None and v > UNDEFINED_DATE:
                    matches |= book_ids
            return matches

        for k, relop in iteritems(self.operators):
            if query.startswith(k):
                query = query[len(k):]
                break
        else:
            relop = self.operators['=']

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
                    raise ParseException(_('Number conversion error: {0}').format(num))
                field_count = 3
            else:
                try:
                    qd = parse_date(query, as_utc=False)
                except:
                    raise ParseException(_('Date conversion error: {0}').format(query))
                if '-' in query:
                    field_count = query.count('-') + 1
                else:
                    field_count = query.count('/') + 1

        for v, book_ids in field_iter():
            if isinstance(v, string_or_bytes):
                v = parse_date(v)
            if v is not None and relop(dt_as_local(v), qd, field_count):
                matches |= book_ids

        return matches
# }}}


class NumericSearch:  # {{{

    def __init__(self):
        self.operators = OrderedDict((
            ('!=', operator.ne),
            ('>=', operator.ge),
            ('<=', operator.le),
            ('=', operator.eq),
            ('>', operator.gt),
            ('<', operator.lt),
        ))

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
            for k, relop in iteritems(self.operators):
                if query.startswith(k):
                    query = query[len(k):]
                    break
            else:
                relop = self.operators['=']

            if dt == 'rating':
                cast = lambda x: 0 if x is None else int(x)
                adjust = lambda x: x // 2
            else:
                # Datatype is empty if the source is a template. Assume float
                cast = float if dt in ('float', 'composite', 'half-rating', '') else int

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
            except Exception:
                raise ParseException(
                        _('Non-numeric value in query: {0}').format(query))
            if dt == 'half-rating':
                q = int(round(q * 2))
                cast = int

        qfalse = query == 'false'
        for val, book_ids in field_iter():
            if val is None:
                if qfalse:
                    matches |= book_ids
                continue
            try:
                v = cast(val)
            except Exception:
                v = None
            if v:
                v = adjust(v)
            if relop(v, q):
                matches |= book_ids
        return matches

# }}}


class BooleanSearch:  # {{{

    def __init__(self):
        self.local_no        = icu_lower(_('no'))
        self.local_yes       = icu_lower(_('yes'))
        self.local_unchecked = icu_lower(_('unchecked'))
        self.local_checked   = icu_lower(_('checked'))
        self.local_empty     = icu_lower(_('empty'))
        self.local_blank     = icu_lower(_('blank'))
        self.local_bool_values = {
            self.local_no, self.local_unchecked, '_no', 'false', 'no', 'unchecked', '_unchecked',
            self.local_yes, self.local_checked, 'checked', '_checked', '_yes', 'true', 'yes',
            self.local_empty, self.local_blank, 'blank', '_blank', '_empty', 'empty'}

    def __call__(self, query, field_iter, bools_are_tristate):
        matches = set()
        if query not in self.local_bool_values:
            raise ParseException(_('Invalid boolean query "{0}"').format(query))
        for val, book_ids in field_iter():
            val = force_to_bool(val)
            if not bools_are_tristate:
                if val is None or not val:  # item is None or set to false
                    if query in {self.local_no, self.local_unchecked, 'unchecked', '_unchecked', 'no', '_no', 'false'}:
                        matches |= book_ids
                else:  # item is explicitly set to true
                    if query in {self.local_yes, self.local_checked, 'checked', '_checked', 'yes', '_yes', 'true'}:
                        matches |= book_ids
            else:
                if val is None:
                    if query in {self.local_empty, self.local_blank, 'blank', '_blank', 'empty', '_empty', 'false'}:
                        matches |= book_ids
                elif not val:  # is not None and false
                    if query in {self.local_no, self.local_unchecked, 'unchecked', '_unchecked', 'no', '_no', 'true'}:
                        matches |= book_ids
                else:  # item is not None and true
                    if query in {self.local_yes, self.local_checked, 'checked', '_checked', 'yes', '_yes', 'true'}:
                        matches |= book_ids
        return matches

# }}}


class KeyPairSearch:  # {{{

    def __call__(self, query, field_iter, candidates, use_primary_find):
        matches = set()
        if ':' in query:
            q = [q.strip() for q in query.partition(':')[0::2]]
            keyq, valq = q
            keyq_mkind, keyq = _matchkind(keyq)
            valq_mkind, valq = _matchkind(valq)
        else:
            keyq = keyq_mkind = ''
            valq_mkind, valq = _matchkind(query)

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
            for key, val in iteritems(m):
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


class SavedSearchQueries:  # {{{
    queries = {}
    opt_name = ''

    def __init__(self, db, _opt_name):
        self.opt_name = _opt_name
        try:
            self._db = weakref.ref(db)
        except TypeError:
            # db could be None
            self._db = lambda : None
        self.load_from_db()

    def load_from_db(self):
        db = self.db
        if db is not None:
            self.queries = db._pref(self.opt_name, default={})
        else:
            self.queries = {}

    @property
    def db(self):
        return self._db()

    def force_unicode(self, x):
        if not isinstance(x, str):
            x = x.decode(preferred_encoding, 'replace')
        return x

    def add(self, name, value):
        db = self.db
        if db is not None:
            self.queries[self.force_unicode(name)] = self.force_unicode(value).strip()
            db._set_pref(self.opt_name, self.queries)

    def lookup(self, name):
        sn = self.force_unicode(name).lower()
        for n, q in self.queries.items():
            if sn == n.lower():
                return q
        return None

    def delete(self, name):
        db = self.db
        if db is not None:
            self.queries.pop(self.force_unicode(name), False)
            db._set_pref(self.opt_name, self.queries)

    def rename(self, old_name, new_name):
        db = self.db
        if db is not None:
            self.queries[self.force_unicode(new_name)] = self.queries.get(self.force_unicode(old_name), None)
            self.queries.pop(self.force_unicode(old_name), False)
            db._set_pref(self.opt_name, self.queries)

    def set_all(self, smap):
        db = self.db
        if db is not None:
            self.queries = smap
            db._set_pref(self.opt_name, smap)

    def names(self):
        return sorted(self.queries, key=sort_key)
# }}}


class Parser(SearchQueryParser):  # {{{

    def __init__(self, dbcache, all_book_ids, gst, date_search, num_search,
                 bool_search, keypair_search, limit_search_columns, limit_search_columns_to,
                 locations, virtual_fields, lookup_saved_search, parse_cache):
        self.dbcache, self.all_book_ids = dbcache, all_book_ids
        self.all_search_locations = frozenset(locations)
        self.grouped_search_terms = gst
        self.date_search, self.num_search = date_search, num_search
        self.bool_search, self.keypair_search = bool_search, keypair_search
        self.limit_search_columns, self.limit_search_columns_to = (
            limit_search_columns, limit_search_columns_to)
        self.virtual_fields = virtual_fields or {}
        if 'marked' not in self.virtual_fields:
            self.virtual_fields['marked'] = self
        if 'in_tag_browser' not in self.virtual_fields:
            self.virtual_fields['in_tag_browser'] = self
        SearchQueryParser.__init__(self, locations, optimize=True, lookup_saved_search=lookup_saved_search, parse_cache=parse_cache)

    @property
    def field_metadata(self):
        return self.dbcache.field_metadata

    def universal_set(self):
        return self.all_book_ids

    def field_iter(self, name, candidates):
        get_metadata = self.dbcache._get_proxy_metadata
        try:
            field = self.dbcache.fields[name]
        except KeyError:
            field = self.virtual_fields[name]
            self.virtual_field_used = True
        return field.iter_searchable_values(get_metadata, candidates)

    def iter_searchable_values(self, *args, **kwargs):
        for x in ():
            yield x, set()

    def parse(self, *args, **kwargs):
        self.virtual_field_used = False
        return SearchQueryParser.parse(self, *args, **kwargs)

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

        if location == 'vl':
            vl = self.dbcache._pref('virtual_libraries', {}).get(query) if query else None
            if not vl:
                raise ParseException(_('No such Virtual library: {}').format(query))
            try:
                return candidates & self.dbcache.books_in_virtual_library(
                            query, virtual_fields=self.virtual_fields)
            except RuntimeError:
                raise ParseException(_('Virtual library search is recursive: {}').format(query))

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
            raise ParseException(
                       _('Recursive query group detected: {0}').format(query))

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

        upf = prefs['use_primary_find_in_search']

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
                if location == 'id':
                    is_many = False

                    def fi(default_value=None):
                        for qid in candidates:
                            yield qid, {qid}
                else:
                    field = self.dbcache.fields[location]
                    fi, is_many = partial(self.field_iter, location, candidates), field.is_many
                if dt == 'rating' and fm['display'].get('allow_half_stars'):
                    dt = 'half-rating'
                return self.num_search(
                    icu_lower(query), fi, location, dt, candidates, is_many=is_many)

            # take care of the 'count' operator for is_multiples
            if (fm['is_multiple'] and
                len(query) > 1 and query[0] == '#' and query[1] in '=<>!'):
                return self.num_search(icu_lower(query[1:]), partial(
                        self.dbcache.fields[location].iter_counts, candidates,
                        get_metadata=self.dbcache._get_proxy_metadata),
                    location, dt, candidates)

            # take care of boolean special case
            if dt == 'bool':
                return self.bool_search(icu_lower(query),
                                partial(self.field_iter, location, candidates),
                                self.dbcache._pref('bools_are_tristate'))

            # special case: colon-separated fields such as identifiers. isbn
            # is a special case within the case
            if fm.get('is_csp', False):
                field_iter = partial(self.field_iter, location, candidates)
                if location == 'identifiers' and original_location == 'isbn':
                    return self.keypair_search('=isbn:'+query, field_iter,
                                        candidates, upf)
                return self.keypair_search(query, field_iter, candidates, upf)

        # check for user categories
        if len(location) >= 2 and location.startswith('@'):
            return self.get_user_category_matches(location[1:], icu_lower(query), candidates)

        # Everything else (and 'all' matches)
        case_sensitive = prefs['case_sensitive']

        if location == 'template':
            try:
                template, sep, query = regex.split('#@#:([tdnb]):', query, flags=regex.IGNORECASE)
                if sep:
                    sep = sep.lower()
                else:
                    sep = 't'
            except:
                if DEBUG:
                    import traceback
                    traceback.print_exc()
                raise ParseException(_('search template: missing or invalid separator. Valid separators are: {}').format('#@#:[tdnb]:'))
            matchkind, query = _matchkind(query, case_sensitive=case_sensitive)
            matches = set()
            error_string = '*@*TEMPLATE_ERROR*@*'
            template_cache = {}
            global_vars = {}
            for book_id in candidates:
                mi = self.dbcache.get_proxy_metadata(book_id)
                val = mi.formatter.safe_format(template, {}, error_string, mi,
                                            column_name='search template',
                                            template_cache=template_cache,
                                            global_vars=global_vars)
                if val.startswith(error_string):
                    raise ParseException(val[len(error_string):])
                if sep == 't':
                    if _match(query, [val,], matchkind, use_primary_find_in_search=upf,
                              case_sensitive=case_sensitive):
                        matches.add(book_id)
                elif sep == 'n' and val:
                    matches.update(self.num_search(
                        icu_lower(query), {val:{book_id,}}.items, '', '',
                        {book_id,}, is_many=False))
                elif sep == 'd' and val:
                    matches.update(self.date_search(
                            icu_lower(query), {val:{book_id,}}.items))
                elif sep == 'b':
                    matches.update(self.bool_search(icu_lower(query),
                            {'True' if val else 'False':{book_id,}}.items, False))

            return matches

        matchkind, query = _matchkind(query, case_sensitive=case_sensitive)
        all_locs = set()
        text_fields = set()
        field_metadata = {}

        for x, fm in self.field_metadata.iter_items():
            if x.startswith('@'):
                continue
            if fm['search_terms'] and x not in {'series_sort', 'id'}:
                if x not in self.virtual_fields and x != 'uuid':
                    # We dont search virtual fields because if we do, search
                    # caching will not be used
                    all_locs.add(x)
                field_metadata[x] = fm
                if fm['datatype'] in {'composite', 'text', 'comments', 'series', 'enumeration'}:
                    text_fields.add(x)

        locations = all_locs if location == 'all' else {location}

        current_candidates = set(candidates)

        try:
            rating_query = int(float(query)) * 2
        except:
            rating_query = None

        try:
            int_query = int(float(query))
        except:
            int_query = None

        try:
            float_query = float(query)
        except:
            float_query = None

        for location in locations:
            current_candidates -= matches
            q = query
            if location == 'languages':
                q = canonicalize_lang(query)
                if q is None:
                    lm = lang_map()
                    rm = {v.lower():k for k,v in iteritems(lm)}
                    q = rm.get(query, query)

            if matchkind == CONTAINS_MATCH and q.lower() in {'true', 'false'}:
                found = set()
                for val, book_ids in self.field_iter(location, current_candidates):
                    if val and (not hasattr(val, 'strip') or val.strip()):
                        found |= book_ids
                matches |= (found if q.lower() == 'true' else (current_candidates-found))
                continue

            dt = field_metadata.get(location, {}).get('datatype', None)
            if dt == 'rating':
                if rating_query is not None:
                    for val, book_ids in self.field_iter(location, current_candidates):
                        if val == rating_query:
                            matches |= book_ids
                continue

            if dt == 'float':
                if float_query is not None:
                    for val, book_ids in self.field_iter(location, current_candidates):
                        if val == float_query:
                            matches |= book_ids
                continue

            if dt == 'int':
                if int_query is not None:
                    for val, book_ids in self.field_iter(location, current_candidates):
                        if val == int_query:
                            matches |= book_ids
                continue

            if location in text_fields:
                for val, book_ids in self.field_iter(location, current_candidates):
                    if val is not None:
                        if isinstance(val, string_or_bytes):
                            val = (val,)
                        if _match(q, val, matchkind, use_primary_find_in_search=upf, case_sensitive=case_sensitive):
                            matches |= book_ids

            if location == 'series_sort':
                book_lang_map = self.dbcache.fields['languages'].book_value_map
                for val, book_ids in self.dbcache.fields['series'].iter_searchable_values_for_sort(current_candidates, book_lang_map):
                    if val is not None:
                        if _match(q, (val,), matchkind, use_primary_find_in_search=upf, case_sensitive=case_sensitive):
                            matches |= book_ids

        return matches

    def get_user_category_matches(self, location, query, candidates):
        matches = set()
        if len(query) < 2:
            return matches

        user_cats = self.dbcache._pref('user_categories')
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
# }}}


class LRUCache:  # {{{

    'A simple Least-Recently-Used cache'

    def __init__(self, limit=50):
        self.item_map = {}
        self.age_map = deque()
        self.limit = limit

    def _move_up(self, key):
        if key != self.age_map[-1]:
            self.age_map.remove(key)
            self.age_map.append(key)

    def add(self, key, val):
        if key in self.item_map:
            self._move_up(key)
            return

        if len(self.age_map) >= self.limit:
            self.item_map.pop(self.age_map.popleft())

        self.item_map[key] = val
        self.age_map.append(key)
    __setitem__  = add

    def get(self, key, default=None):
        ans = self.item_map.get(key, default)
        if ans is not default:
            self._move_up(key)
        return ans

    def clear(self):
        self.item_map.clear()
        self.age_map.clear()

    def pop(self, key, default=None):
        self.item_map.pop(key, default)
        try:
            self.age_map.remove(key)
        except ValueError:
            pass

    def __contains__(self, key):
        return key in self.item_map

    def __len__(self):
        return len(self.age_map)

    def __getitem__(self, key):
        return self.get(key)

    def __iter__(self):
        return iteritems(self.item_map)
# }}}


class Search:

    MAX_CACHE_UPDATE = 50

    def __init__(self, db, opt_name, all_search_locations=()):
        self.all_search_locations = all_search_locations
        self.date_search = DateSearch()
        self.num_search = NumericSearch()
        self.bool_search = BooleanSearch()
        self.keypair_search = KeyPairSearch()
        self.saved_searches = SavedSearchQueries(db, opt_name)
        self.cache = LRUCache()
        self.parse_cache = LRUCache(limit=100)

    def get_saved_searches(self):
        return self.saved_searches

    def change_locations(self, newlocs):
        if frozenset(newlocs) != frozenset(self.all_search_locations):
            self.clear_caches()
            self.parse_cache.clear()
        self.all_search_locations = newlocs

    def update_or_clear(self, dbcache, book_ids=None):
        if book_ids and (len(book_ids) * len(self.cache)) <= self.MAX_CACHE_UPDATE:
            self.update_caches(dbcache, book_ids)
        else:
            self.clear_caches()

    def clear_caches(self):
        self.cache.clear()

    def update_caches(self, dbcache, book_ids):
        sqp = self.create_parser(dbcache)
        try:
            return self._update_caches(sqp, book_ids)
        finally:
            sqp.dbcache = sqp.lookup_saved_search = None

    def discard_books(self, book_ids):
        book_ids = set(book_ids)
        for query, result in self.cache:
            result.difference_update(book_ids)

    def _update_caches(self, sqp, book_ids):
        book_ids = sqp.all_book_ids = set(book_ids)
        remove = set()
        for query, result in tuple(self.cache):
            try:
                matches = sqp.parse(query)
            except ParseException:
                remove.add(query)
            else:
                # remove books that no longer match
                result.difference_update(book_ids - matches)
                # add books that now match but did not before
                result.update(matches)
        for query in remove:
            self.cache.pop(query)

    def create_parser(self, dbcache, virtual_fields=None):
        return Parser(
            dbcache, set(), dbcache._pref('grouped_search_terms'),
            self.date_search, self.num_search, self.bool_search,
            self.keypair_search,
            prefs['limit_search_columns'],
            prefs['limit_search_columns_to'], self.all_search_locations,
            virtual_fields, self.saved_searches.lookup, self.parse_cache)

    def __call__(self, dbcache, query, search_restriction, virtual_fields=None, book_ids=None):
        '''
        Return the set of ids of all records that match the specified
        query and restriction
        '''
        # We construct a new parser instance per search as the parse is not
        # thread safe.
        sqp = self.create_parser(dbcache, virtual_fields)
        try:
            return self._do_search(sqp, query, search_restriction, dbcache, book_ids=book_ids)
        finally:
            sqp.dbcache = sqp.lookup_saved_search = None

    def query_is_cacheable(self, sqp, dbcache, query):
        if query:
            for name, value in sqp.get_queried_fields(query):
                if name == 'template' and '#@#:d:' in value:
                    return False
                elif name in dbcache.field_metadata.all_field_keys():
                    fm = dbcache.field_metadata[name]
                    if fm['datatype'] == 'datetime':
                        return False
                    if fm['datatype'] == 'composite':
                        if fm.get('display', {}).get('composite_sort', '') == 'date':
                            return False
        return True

    def _do_search(self, sqp, query, search_restriction, dbcache, book_ids=None):
        ''' Do the search, caching the results. Results are cached only if the
        search is on the full library and no virtual field is searched on '''
        if isinstance(search_restriction, bytes):
            search_restriction = search_restriction.decode('utf-8')
        if isinstance(query, bytes):
            query = query.decode('utf-8')

        query = query.strip()
        use_cache = self.query_is_cacheable(sqp, dbcache, query)

        if use_cache and book_ids is None and query and not search_restriction:
            cached = self.cache.get(query)
            if cached is not None:
                return cached

        restricted_ids = all_book_ids = dbcache._all_book_ids(type=set)
        if search_restriction and search_restriction.strip():
            sr = search_restriction.strip()
            sqp.all_book_ids = all_book_ids if book_ids is None else book_ids
            if self.query_is_cacheable(sqp, dbcache, sr):
                cached = self.cache.get(sr)
                if cached is None:
                    restricted_ids = sqp.parse(sr)
                    if not sqp.virtual_field_used and sqp.all_book_ids is all_book_ids:
                        self.cache.add(sr, restricted_ids)
                else:
                    restricted_ids = cached
                    if book_ids is not None:
                        restricted_ids = book_ids.intersection(restricted_ids)
            else:
                restricted_ids = sqp.parse(sr)
        elif book_ids is not None:
            restricted_ids = book_ids

        if not query:
            return restricted_ids

        if use_cache and restricted_ids is all_book_ids:
            cached = self.cache.get(query)
            if cached is not None:
                return cached

        sqp.all_book_ids = restricted_ids
        result = sqp.parse(query)

        if not sqp.virtual_field_used and sqp.all_book_ids is all_book_ids:
            self.cache.add(query, result)

        return result
