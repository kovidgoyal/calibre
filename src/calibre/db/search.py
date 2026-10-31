#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

import operator
import unicodedata
import weakref
from collections import OrderedDict, deque
from collections.abc import Callable
from datetime import datetime, timedelta
from functools import partial
from typing import TYPE_CHECKING, cast

import regex

from calibre.constants import DEBUG, preferred_encoding
from calibre.db.utils import force_to_bool
from calibre.utils.config_base import prefs
from calibre.utils.date import UNDEFINED_DATE, dt_as_local, local_tz, now, parse_date
from calibre.utils.icu import ascii_primary_no_punc_matcher, primary_contains, primary_no_punc_contains, sort_key
from calibre.utils.icu import lower as icu_lower
from calibre.utils.localization import _, canonicalize_lang, lang_map
from calibre.utils.search_query_parser import ParseException, SearchQueryParser

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Iterator
    from typing import Protocol

    from calibre.db.cache import Cache
    from calibre.db.lazy import ProxyMetadata
    from calibre.library.field_metadata import FieldMetadata
    from calibre.utils.search_query_parser import ParseTree

    # A callable that returns an iterable of (field value, ids of books with that value)
    type FieldIter = Callable[[], Iterable[tuple[object, set[int]]]]

    class VirtualField(Protocol):
        def iter_searchable_values(self, get_metadata: Callable[[int], ProxyMetadata], candidates: Iterable[int], /) -> Iterable[tuple[object, set[int]]]: ...


CONTAINS_MATCH = 0
EQUALS_MATCH = 1
REGEXP_MATCH = 2
ACCENT_MATCH = 3


class TemplatesNotAllowed(ParseException):
    pass


# Utils {{{


def _matchkind(query: str, case_sensitive: bool = False) -> tuple[int, str]:
    matchkind = CONTAINS_MATCH
    if len(query) > 1:
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


def _match(query: str, value: Iterable[str], matchkind: int, use_primary_find_in_search: bool = True, case_sensitive: bool = False) -> bool:
    if query.startswith('..'):
        query = query[1:]
        sq = query[1:]
        internal_match_ok = True
    else:
        internal_match_ok = False
    if matchkind == CONTAINS_MATCH and not case_sensitive and use_primary_find_in_search:
        # This is the hot path when searching, so avoid the ICU functions,
        # which are slow in larger libraries, for ASCII only text
        ascii_matcher = ascii_primary_no_punc_matcher(query)
        if ascii_matcher is None:
            return any(primary_no_punc_contains(query, icu_lower(t)) for t in value)
        # ruff: ignore[reimplemented-builtin]
        for t in value:
            if ascii_matcher(t) if t.isascii() else primary_no_punc_contains(query, icu_lower(t)):
                return True
        return False
    for t in value:
        if not case_sensitive:
            t = icu_lower(t)
        if matchkind == EQUALS_MATCH:
            if internal_match_ok:
                if query == t:
                    return True
                return sq in (c.strip() for c in t.split('.') if c.strip())
            elif query[0] == '.':
                if t.startswith(query[1:]):
                    ql = len(query) - 1
                    if len(t) == ql or t[ql : ql + 1] == '.':
                        return True
            elif query == t:
                return True
        elif matchkind == REGEXP_MATCH:
            flags = regex.UNICODE | regex.VERSION1 | regex.FULLCASE | (0 if case_sensitive else regex.IGNORECASE)
            try:
                if regex.search(query, t, flags) is not None:
                    return True
            except regex.error as e:
                raise ParseException(_('Invalid regular expression: {!r} with error: {}').format(query, str(e)))
        elif matchkind == ACCENT_MATCH:
            if primary_contains(query, t):
                return True
        elif matchkind == CONTAINS_MATCH:
            # The case insensitive primary match is handled by the fast path above
            if query in t:
                return True
    return False


# }}}


def months_ago(dt: datetime, num: int) -> datetime:
    """Return the first day of the month that is num months before the month of dt"""
    year, month = divmod(dt.year * 12 + dt.month - 1 - num, 12)
    return dt.replace(year=year, month=month + 1, day=1)


class DateSearch:  # {{{
    def __init__(self) -> None:
        self.operators = OrderedDict((
            ('!=', self.ne),
            ('>=', self.ge),
            ('<=', self.le),
            ('=', self.eq),
            ('>', self.gt),
            ('<', self.lt),
        ))
        # NOTE: The following strings are keywords used in date searches, such
        # as date:thismonth or date:>3daysago. Their translations must be
        # single words without spaces.
        self.local_today = {'_today', 'today', icu_lower(_('today'))}
        self.local_yesterday = {'_yesterday', 'yesterday', icu_lower(_('yesterday'))}
        self.local_thismonth = {'_thismonth', 'thismonth', icu_lower(_('thismonth'))}
        self.local_lastmonth = {'_lastmonth', 'lastmonth', icu_lower(_('lastmonth'))}
        self.local_thisyear = {'_thisyear', 'thisyear', icu_lower(_('thisyear'))}
        self.local_lastyear = {'_lastyear', 'lastyear', icu_lower(_('lastyear'))}
        self.ago_pats = tuple(
            (regex.compile(rf'({regex.escape(local)}|{unit}|_{unit})$', flags=regex.UNICODE | regex.VERSION1), unit)
            for local, unit in ((_('daysago'), 'daysago'), (_('monthsago'), 'monthsago'), (_('yearsago'), 'yearsago'))
        )
        # dateutil reads month.year and year.month as decimal numbers
        self.dotted_month_year_pat = regex.compile(r'(?:\d{1,2}\.\d{4}|\d{4}\.\d{1,2})')

    def specified_field_count(self, query: str) -> int:
        # Parse with two defaults that differ in every field, any field that
        # comes out the same in both was present in the query. The defaults
        # are in leap years and in months with 31 days so that every valid
        # day and month in the query can be combined with them.
        a = parse_date(query, as_utc=False, default=datetime(2000, 1, 1, tzinfo=local_tz))
        b = parse_date(query, as_utc=False, default=datetime(2004, 3, 2, tzinfo=local_tz))
        if a.month != b.month:
            return 1
        return 2 if a.day != b.day else 3

    def eq(self, dbdate: datetime, query: datetime, field_count: int) -> bool:
        if dbdate.year == query.year:
            if field_count == 1:
                return True
            if dbdate.month == query.month:
                if field_count == 2:
                    return True
                return dbdate.day == query.day
        return False

    def ne(self, *args: *tuple[datetime, datetime, int]) -> bool:
        return not self.eq(*args)

    def gt(self, dbdate: datetime, query: datetime, field_count: int) -> bool:
        if dbdate.year > query.year:
            return True
        if field_count > 1 and dbdate.year == query.year:
            if dbdate.month > query.month:
                return True
            return field_count == 3 and dbdate.month == query.month and dbdate.day > query.day
        return False

    def le(self, *args: *tuple[datetime, datetime, int]) -> bool:
        return not self.gt(*args)

    def lt(self, dbdate: datetime, query: datetime, field_count: int) -> bool:
        if dbdate.year < query.year:
            return True
        if field_count > 1 and dbdate.year == query.year:
            if dbdate.month < query.month:
                return True
            return field_count == 3 and dbdate.month == query.month and dbdate.day < query.day
        return False

    def ge(self, *args: *tuple[datetime, datetime, int]) -> bool:
        return not self.lt(*args)

    def __call__(self, query: str, field_iter: FieldIter) -> set[int]:
        matches: set[int] = set()
        if len(query) < 2:
            return matches

        if query == 'false':
            for v, book_ids in field_iter():
                if isinstance(v, (bytes, str)):
                    if isinstance(v, bytes):
                        v = v.decode(preferred_encoding, 'replace')
                    v = parse_date(v)
                if v is None or v <= UNDEFINED_DATE:  # ty: ignore[unsupported-operator]
                    matches |= book_ids
            return matches

        if query == 'true':
            for v, book_ids in field_iter():
                if isinstance(v, (bytes, str)):
                    if isinstance(v, bytes):
                        v = v.decode(preferred_encoding, 'replace')
                    v = parse_date(v)
                if v is not None and v > UNDEFINED_DATE:  # ty: ignore[unsupported-operator]
                    matches |= book_ids
            return matches

        for k, relop in self.operators.items():
            if query.startswith(k):
                query = query[len(k) :]
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
        elif query in self.local_lastmonth:
            qd = months_ago(now(), 1)
            field_count = 2
        elif query in self.local_thisyear:
            qd = now()
            field_count = 1
        elif query in self.local_lastyear:
            qd = months_ago(now(), 12)
            field_count = 1
        else:
            m = unit = None
            for pat, unit in self.ago_pats:
                if (m := pat.search(query)) is not None:
                    break
            if m is not None:
                num = query[: -len(m.group(1))]
                try:
                    num = int(num)
                except ValueError:
                    raise ParseException(_('Number conversion error: {0}').format(num))
                try:
                    if unit == 'daysago':
                        qd, field_count = now() - timedelta(num), 3
                    elif unit == 'monthsago':
                        qd, field_count = months_ago(now(), num), 2
                    else:
                        qd, field_count = months_ago(now(), 12 * num), 1
                except ValueError, OverflowError:
                    raise ParseException(_('Date out of range: {0}').format(query))
            else:
                if self.dotted_month_year_pat.fullmatch(query) is not None:
                    query = query.replace('.', '-')
                try:
                    qd = parse_date(query, as_utc=False)
                    field_count = self.specified_field_count(query)
                except Exception:
                    raise ParseException(_('Date conversion error: {0}').format(query))

        for v, book_ids in field_iter():
            if isinstance(v, (str, bytes)):
                v = parse_date(v)
            if v is not None and relop(dt_as_local(v), qd, field_count):  # ty: ignore[invalid-argument-type]
                matches |= book_ids

        return matches


# }}}


class NumericSearch:  # {{{
    def __init__(self) -> None:
        self.operators = OrderedDict((
            ('!=', operator.ne),
            ('>=', operator.ge),
            ('<=', operator.le),
            ('=', operator.eq),
            ('>', operator.gt),
            ('<', operator.lt),
        ))

    def __call__(self, query: str, field_iter: FieldIter, location: str, datatype: str, candidates: set[int], is_many: bool = False) -> set[int]:
        matches: set[int] = set()
        if not query:
            return matches

        q = ''
        cast = adjust = lambda x: x
        dt = datatype

        if is_many and query in {'true', 'false'}:
            if datatype == 'rating':

                def valcheck(x: object) -> bool:
                    return x is not None and x > 0  # ty: ignore[unsupported-operator]

            else:

                def valcheck(x: object) -> bool:
                    return True

            found: set[int] = set()
            for val, book_ids in field_iter():
                if valcheck(val):
                    found |= book_ids
            return found if query == 'true' else candidates - found

        if query == 'false':
            if location == 'cover':

                def relop(x: object, y: object) -> bool:
                    return not bool(x)

            else:

                def relop(x: object, y: object) -> bool:
                    return x is None

        elif query == 'true':
            if location == 'cover':

                def relop(x: object, y: object) -> bool:
                    return bool(x)

            else:

                def relop(x: object, y: object) -> bool:
                    return x is not None

        else:
            for k, relop in self.operators.items():
                if query.startswith(k):
                    query = query[len(k) :]
                    break
            else:
                relop = self.operators['=']

            cast: Callable[..., int | float]
            if dt == 'rating':

                def _cast_for_rating(x: str | float | None) -> int:
                    return 0 if x is None else int(x)

                cast = _cast_for_rating

                def adjust(x: float) -> float:
                    return x // 2

            else:
                # Datatype is empty if the source is a template. Assume float
                cast = float if dt in ('float', 'composite', 'half-rating', '') else int

            mult = 1.0
            if len(query) > 1:
                mult = query[-1].lower()
                mult = {'k': 1024.0, 'm': 1024.0**2, 'g': 1024.0**3}.get(mult, 1.0)
                if mult != 1.0:
                    query = query[:-1]
            else:
                mult = 1.0

            try:
                q = cast(query) * mult
            except Exception:
                raise ParseException(_('Non-numeric value in query: {0}').format(query))
            if dt == 'half-rating':
                try:
                    q = round(q * 2)
                    cast = int
                except ValueError, OverflowError:
                    # nan or inf cannot be rounded, compare them as floats so
                    # that nan matches nothing and inf compares as expected
                    q *= 2

        qfalse = query == 'false'
        for val, book_ids in field_iter():
            if val is None:
                if qfalse:
                    matches |= book_ids
                continue
            try:
                v = cast(val)  # ty: ignore[invalid-argument-type]
            except Exception:
                raise ParseException(_('Non-numeric value in column {0}: {1}').format(location, val))
            if v:
                v = adjust(v)
            if relop(v, q):
                matches |= book_ids
        return matches


# }}}

nfc = partial(unicodedata.normalize, 'NFC')
nfkc = partial(unicodedata.normalize, 'NFKC')
nfkd = partial(unicodedata.normalize, 'NFKD')
nfd = partial(unicodedata.normalize, 'NFD')


def local_forms(x: str) -> set[str]:
    x = icu_lower(x)
    return {nfc(x), nfd(x), nfkc(x), nfkd(x)}


class BooleanSearch:  # {{{
    def __init__(self) -> None:
        local_no = local_forms(_('No')) | local_forms(_('no'))
        local_yes = local_forms(_('Yes')) | local_forms(_('yes'))
        local_unchecked = local_forms(_('unchecked'))
        local_checked = local_forms(_('checked'))
        local_empty = local_forms(_('empty'))
        local_blank = local_forms(_('blank'))

        self.valid_bool_values = frozenset(
            {
                '_no',
                'false',
                'no',
                'unchecked',
                '_unchecked',
                'checked',
                '_checked',
                '_yes',
                'true',
                'yes',
                'blank',
                '_blank',
                '_empty',
                'empty',
            }
            | local_no
            | local_yes
            | local_unchecked
            | local_checked
            | local_empty
            | local_blank
        )
        self.no_and_unchecked = frozenset({'unchecked', '_unchecked', 'no', '_no', 'false'} | local_no | local_unchecked)
        self.no_and_unchecked_with_true = frozenset({'unchecked', '_unchecked', 'no', '_no', 'true'} | local_no | local_unchecked)
        self.yes_and_checked = frozenset({'checked', '_checked', 'yes', '_yes', 'true'} | local_yes | local_checked)
        self.empty_and_blank = frozenset({'blank', '_blank', 'empty', '_empty', 'false'} | local_empty | local_blank)

    def __call__(self, query: str, field_iter: FieldIter, bools_are_tristate: object) -> set[int]:
        matches: set[int] = set()
        if query not in self.valid_bool_values:
            raise ParseException(_('Invalid boolean query "{0}"').format(query))
        for val, book_ids in field_iter():
            val = force_to_bool(val)
            if not bools_are_tristate:
                if val is None or not val:  # item is None or set to false
                    if query in self.no_and_unchecked:
                        matches |= book_ids
                elif query in self.yes_and_checked:
                    matches |= book_ids
            elif val is None:
                if query in self.empty_and_blank:
                    matches |= book_ids
            elif not val:  # is not None and false
                if query in self.no_and_unchecked_with_true:
                    matches |= book_ids
            elif query in self.yes_and_checked:
                matches |= book_ids
        return matches


# }}}


class KeyPairSearch:  # {{{
    def __call__(self, query: str, field_iter: FieldIter, candidates: set[int], use_primary_find: bool) -> set[int]:
        matches: set[int] = set()
        if ':' in query:
            q = [q.strip() for q in query.partition(':')[0::2]]
            keyq, valq = q
            keyq_mkind, keyq = _matchkind(keyq)
            valq_mkind, valq = _matchkind(valq)
        else:
            keyq = keyq_mkind = ''
            valq_mkind, valq = _matchkind(query)

        if valq in {'true', 'false'}:
            found: set[int] = set()
            if keyq:
                for val, book_ids in field_iter():
                    if val and val.get(keyq, False):  # ty: ignore[unresolved-attribute]
                        found |= book_ids
            else:
                for val, book_ids in field_iter():
                    if val:
                        found |= book_ids
            return found if valq == 'true' else candidates - found

        for m, book_ids in field_iter():
            for key, val in m.items():  # ty: ignore[unresolved-attribute]
                if keyq and not _match(keyq, (key,), keyq_mkind, use_primary_find_in_search=use_primary_find):  # ty: ignore[invalid-argument-type]
                    continue
                if valq and not _match(valq, (val,), valq_mkind, use_primary_find_in_search=use_primary_find):
                    continue
                matches |= book_ids
                break

        return matches


# }}}


class SavedSearchQueries:  # {{{
    queries: dict[str, str] = {}
    opt_name: str = ''

    def __init__(self, db: Cache | None, _opt_name: str) -> None:
        self.opt_name = _opt_name
        self._db: Callable[[], Cache | None]
        try:
            self._db = weakref.ref(db)
        except TypeError:
            # db could be None
            self._db = lambda: None
        self.load_from_db()

    def load_from_db(self) -> None:
        db = self.db
        if db is not None:
            self.queries = db._pref(self.opt_name, default={})
        else:
            self.queries = {}

    @property
    def db(self) -> Cache | None:
        return self._db()

    def force_unicode(self, x: str | bytes) -> str:
        if not isinstance(x, str):
            x = x.decode(preferred_encoding, 'replace')
        return x

    def add(self, name: str | bytes, value: str | bytes) -> None:
        db = self.db
        if db is not None:
            self.queries[self.force_unicode(name)] = self.force_unicode(value).strip()
            db._set_pref(self.opt_name, self.queries)

    def lookup(self, name: str | bytes) -> str | None:
        sn = self.force_unicode(name).lower()
        for n, q in self.queries.items():
            if sn == n.lower():
                return q
        return None

    def delete(self, name: str | bytes) -> None:
        db = self.db
        if db is not None:
            self.queries.pop(self.force_unicode(name), False)
            db._set_pref(self.opt_name, self.queries)

    def rename(self, old_name: str | bytes, new_name: str | bytes) -> None:
        db = self.db
        if db is not None:
            self.queries[self.force_unicode(new_name)] = self.queries.get(self.force_unicode(old_name), None)  # ty: ignore[invalid-assignment]
            self.queries.pop(self.force_unicode(old_name), False)
            db._set_pref(self.opt_name, self.queries)

    def set_all(self, smap: dict[str, str]) -> None:
        db = self.db
        if db is not None:
            self.queries = smap
            db._set_pref(self.opt_name, smap)

    def names(self) -> list[str]:
        return sorted(self.queries, key=sort_key)


# }}}


class Parser(SearchQueryParser):  # {{{
    def __init__(
        self,
        dbcache: Cache,
        all_book_ids: set[int],
        gst: dict[str, list[str]],
        date_search: DateSearch,
        num_search: NumericSearch,
        bool_search: BooleanSearch,
        keypair_search: KeyPairSearch,
        limit_search_columns: bool,
        limit_search_columns_to: Collection[str],
        locations: Collection[str],
        virtual_fields: dict[str, VirtualField] | None,
        lookup_saved_search: Callable[[str], str | None],
        parse_cache: LRUCache[str, ParseTree],
        allow_templates: bool = True,
    ) -> None:
        self.allow_templates = allow_templates
        self.dbcache, self.all_book_ids = dbcache, all_book_ids
        self.all_search_locations = frozenset(locations)
        self.grouped_search_terms = gst
        self.date_search, self.num_search = date_search, num_search
        self.bool_search, self.keypair_search = bool_search, keypair_search
        self.limit_search_columns, self.limit_search_columns_to = (limit_search_columns, limit_search_columns_to)
        self.virtual_fields: dict[str, VirtualField] = virtual_fields or {}
        if 'marked' not in self.virtual_fields:
            self.virtual_fields['marked'] = self
        if 'in_tag_browser' not in self.virtual_fields:
            self.virtual_fields['in_tag_browser'] = self
        SearchQueryParser.__init__(self, locations, optimize=True, lookup_saved_search=lookup_saved_search, parse_cache=parse_cache)

    @property
    def field_metadata(self) -> FieldMetadata:
        return self.dbcache.field_metadata

    def universal_set(self) -> set[int]:
        return self.all_book_ids

    def field_iter(self, name: str, candidates: set[int]) -> Iterable[tuple[object, set[int]]]:
        get_metadata = self.dbcache._get_proxy_metadata
        try:
            field = self.dbcache.fields[name]
        except KeyError:
            field = self.virtual_fields[name]
            self.virtual_field_used = True
        return field.iter_searchable_values(get_metadata, candidates)

    def iter_searchable_values(self, *args: object, **kwargs: object) -> Iterator[tuple[object, set[int]]]:
        for x in ():
            yield x, set()

    def parse(self, *args: str | set[int] | None, **kwargs: str | set[int] | None) -> set[int]:
        self.virtual_field_used = False
        return SearchQueryParser.parse(self, *args, **kwargs)  # ty: ignore[invalid-argument-type]

    def get_matches(self, location: str, query: str, candidates: set[int] | None = None, allow_recursion: bool = True) -> set[int]:
        # If candidates is not None, it must not be modified. Changing its
        # value will break query optimization in the search parser
        matches: set[int] = set()

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
                return candidates & self.dbcache.books_in_virtual_library(query, virtual_fields=self.virtual_fields)
            except RuntimeError:
                raise ParseException(_('Virtual library search is recursive: {}').format(query))

        if len(location) > 2 and location.startswith('@') and location[1:] in self.grouped_search_terms:
            location = location[1:]

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
                    c = candidates.copy()
                    m = self.get_matches(loc, query, candidates=c, allow_recursion=False)
                    matches |= m
                    c -= m
                    if len(c) == 0:
                        break
                if invert:
                    matches = self.all_book_ids - matches
                return matches
            raise ParseException(_('Recursive query group detected: {0}').format(query))

        # If the user has asked to restrict searching over all field, apply
        # that restriction
        if location == 'all' and self.limit_search_columns and self.limit_search_columns_to:
            terms = set()
            for l in self.limit_search_columns_to:
                l = icu_lower(l.strip())
                if l and l != 'all' and l in self.all_search_locations:
                    terms.add(l)
            if terms:
                c = candidates.copy()
                for l in terms:
                    try:
                        m = self.get_matches(l, query, candidates=c, allow_recursion=allow_recursion)
                        matches |= m
                        c -= m
                        if len(c) == 0:
                            break
                    except Exception:
                        pass
                return matches

        upf = prefs['use_primary_find_in_search']

        if location in self.field_metadata:
            fm = self.field_metadata[location]
            dt = fm['datatype']

            # take care of dates special case
            if dt == 'datetime' or (dt == 'composite' and fm['display'].get('composite_sort', '') == 'date'):
                if location == 'date':
                    location = 'timestamp'
                return self.date_search(icu_lower(query), partial(self.field_iter, location, candidates))

            # take care of numbers special case
            if dt in ('rating', 'int', 'float') or (dt == 'composite' and fm['display'].get('composite_sort', '') == 'number'):
                if location == 'id':
                    is_many = False

                    def fi(default_value: object = None) -> Iterator[tuple[int, set[int]]]:
                        for qid in candidates:
                            yield qid, {qid}

                else:
                    field = self.dbcache.fields[location]
                    fi, is_many = partial(self.field_iter, location, candidates), field.is_many
                if dt == 'rating' and fm['display'].get('allow_half_stars'):
                    dt = 'half-rating'
                return self.num_search(icu_lower(query), fi, location, dt, candidates, is_many=is_many)

            # take care of the 'count' operator for is_multiples
            if fm['is_multiple'] and len(query) > 1 and query[0] == '#' and query[1] in '=<>!':
                return self.num_search(
                    icu_lower(query[1:]),
                    partial(
                        self.dbcache.fields[location].iter_counts,
                        candidates,
                        get_metadata=self.dbcache._get_proxy_metadata,
                    ),
                    location,
                    dt,
                    candidates,
                )

            # take care of boolean special case
            if dt == 'bool':
                return self.bool_search(
                    icu_lower(query),
                    partial(self.field_iter, location, candidates),
                    self.dbcache._pref('bools_are_tristate'),
                )

            # special case: colon-separated fields such as identifiers. isbn
            # is a special case within the case
            if fm.get('is_csp', False):
                field_iter = partial(self.field_iter, location, candidates)
                if location == 'identifiers' and original_location == 'isbn':
                    return self.keypair_search('=isbn:' + query, field_iter, candidates, upf)
                return self.keypair_search(query, field_iter, candidates, upf)

        # check for user categories
        if len(location) >= 2 and location.startswith('@'):
            return self.get_user_category_matches(location[1:], icu_lower(query), candidates)

        # Everything else (and 'all' matches)
        case_sensitive = prefs['case_sensitive']

        if location == 'template':
            if not self.allow_templates:
                raise TemplatesNotAllowed(_('Templates are not allowed in search expressions'))
            try:
                template, sep, query = regex.split(r'#@#:([tdnb]):', query, flags=regex.IGNORECASE)
                if sep:
                    sep = sep.lower()
                else:
                    sep = 't'
            except Exception:
                if DEBUG:
                    import traceback

                    traceback.print_exc()
                raise ParseException(_('search template: missing or invalid separator. Valid separators are: {}').format('#@#:[tdnb]:'))
            matchkind, query = _matchkind(query, case_sensitive=case_sensitive)
            matches = set()
            error_string = '*@*TEMPLATE_ERROR*@*'
            template_cache = {}
            global_vars = {'_candidates': candidates}
            for book_id in candidates:
                mi = self.dbcache.get_proxy_metadata(book_id)
                val = mi.formatter.safe_format(
                    template,
                    {},
                    error_string,
                    mi,
                    column_name='search template',
                    template_cache=template_cache,
                    global_vars=global_vars,  # ty: ignore[invalid-argument-type]
                    database=self.dbcache,
                )
                if val.startswith(error_string):
                    raise ParseException(val[len(error_string) :])
                if sep == 't':
                    if _match(
                        query,
                        [
                            val,
                        ],
                        matchkind,
                        use_primary_find_in_search=upf,
                        case_sensitive=case_sensitive,
                    ):
                        matches.add(book_id)
                elif sep == 'n' and val:
                    matches.update(
                        self.num_search(
                            icu_lower(query),
                            {
                                val: {
                                    book_id,
                                }
                            }.items,
                            '',
                            '',
                            {
                                book_id,
                            },
                            is_many=False,
                        )
                    )
                elif sep == 'd' and val:
                    matches.update(
                        self.date_search(
                            icu_lower(query),
                            {
                                val: {
                                    book_id,
                                }
                            }.items,
                        )
                    )
                elif sep == 'b':
                    matches.update(
                        self.bool_search(
                            icu_lower(query),
                            {
                                'True' if val else 'False': {
                                    book_id,
                                }
                            }.items,
                            False,
                        )
                    )

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
                    # We don't search virtual fields because if we do, search
                    # caching will not be used
                    all_locs.add(x)
                field_metadata[x] = fm
                if fm['datatype'] in {'composite', 'text', 'comments', 'series', 'enumeration'}:
                    text_fields.add(x)

        locations = all_locs if location == 'all' else {location}

        current_candidates = set(candidates)

        try:
            float_query = float(query)
        except ValueError:
            float_query = None
        # Only whole numbers can match int columns. Ratings are stored as twice
        # the number of stars and are matched the same way num_search() does
        # for queries that specify the field: half star columns round to the
        # nearest half star, other columns only match whole stars.
        int_query = half_rating_query = None
        if float_query is not None:
            try:
                # Parse directly to avoid losing precision for large values
                int_query = int(query)
            except ValueError:
                if float_query.is_integer():
                    int_query = int(float_query)
            try:
                half_rating_query = round(float_query * 2)
            except ValueError, OverflowError:
                # nan or inf cannot match any rating
                half_rating_query = None

        for location in locations:
            current_candidates -= matches
            q = query
            if location == 'languages':
                q = canonicalize_lang(query)
                if q is None:
                    lm = lang_map()
                    rm = {v.lower(): k for k, v in lm.items()}
                    q = rm.get(query, query)

            if matchkind == CONTAINS_MATCH and q.lower() in {'true', 'false'}:
                found = set()
                for val, book_ids in self.field_iter(location, current_candidates):
                    if val and (not hasattr(val, 'strip') or val.strip()):  # ty: ignore[call-non-callable]
                        found |= book_ids
                matches |= found if q.lower() == 'true' else (current_candidates - found)
                continue

            dt = field_metadata.get(location, {}).get('datatype', None)
            if dt == 'rating':
                if field_metadata[location]['display'].get('allow_half_stars'):
                    if half_rating_query is not None:
                        for val, book_ids in self.field_iter(location, current_candidates):
                            if val == half_rating_query:
                                matches |= book_ids
                elif int_query is not None:
                    for val, book_ids in self.field_iter(location, current_candidates):
                        if val is not None and val // 2 == int_query:  # ty: ignore[unsupported-operator]
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
                        if isinstance(val, (str, bytes)):
                            val = (val,)
                        if _match(q, val, matchkind, use_primary_find_in_search=upf, case_sensitive=case_sensitive):  # ty: ignore[invalid-argument-type]
                            matches |= book_ids

            if location == 'series_sort':
                book_lang_map = self.dbcache.fields['languages'].book_value_map
                for val, book_ids in self.dbcache.fields['series'].iter_searchable_values_for_sort(current_candidates, book_lang_map):
                    if val is not None:
                        if _match(q, (val,), matchkind, use_primary_find_in_search=upf, case_sensitive=case_sensitive):
                            matches |= book_ids

        return matches

    def get_user_category_matches(self, location: str, query: str, candidates: set[int]) -> set[int]:
        matches: set[int] = set()
        if len(query) < 2:
            return matches

        user_cats = cast('dict[str, list[tuple[str, str, int]]]', self.dbcache._pref('user_categories'))
        c = set(candidates)

        if query.startswith('.'):
            check_subcats = True
            query = query[1:]
        else:
            check_subcats = False

        for key in user_cats:
            if key == location or (check_subcats and key.startswith(location + '.')):
                for item, category, ign in user_cats[key]:
                    s = self.get_matches(category, '=' + item, candidates=c)
                    c -= s
                    matches |= s
        if query == 'false':
            return candidates - matches
        return matches


# }}}


class LRUCache[K, V]:  # {{{
    "A simple Least-Recently-Used cache"

    def __init__(self, limit: int = 50) -> None:
        self.item_map: dict[K, V] = {}
        self.age_map: deque[K] = deque()
        self.limit = limit

    def _move_up(self, key: K) -> None:
        if key != self.age_map[-1]:
            self.age_map.remove(key)
            self.age_map.append(key)

    def add(self, key: K, val: V) -> None:
        if key in self.item_map:
            self._move_up(key)
            return

        if len(self.age_map) >= self.limit:
            self.item_map.pop(self.age_map.popleft())

        self.item_map[key] = val
        self.age_map.append(key)

    __setitem__ = add

    def get(self, key: K, default: V | None = None) -> V | None:
        ans = self.item_map.get(key, default)
        if ans is not default:
            self._move_up(key)
        return ans

    def clear(self) -> None:
        self.item_map.clear()
        self.age_map.clear()

    def pop(self, key: K, default: V | None = None) -> None:
        self.item_map.pop(key, default)
        try:
            self.age_map.remove(key)
        except ValueError:
            pass

    def __contains__(self, key: object) -> bool:
        return key in self.item_map

    def __len__(self) -> int:
        return len(self.age_map)

    def __getitem__(self, key: K) -> V | None:
        return self.get(key)

    def __iter__(self) -> Iterator[tuple[K, V]]:
        yield from self.item_map.items()


# }}}


class Search:
    MAX_CACHE_UPDATE = 50

    def __init__(self, db: Cache | None, opt_name: str, all_search_locations: Collection[str] = ()) -> None:
        self.all_search_locations = all_search_locations
        self.date_search = DateSearch()
        self.num_search = NumericSearch()
        self.bool_search = BooleanSearch()
        self.keypair_search = KeyPairSearch()
        self.saved_searches = SavedSearchQueries(db, opt_name)
        self.cache: LRUCache[str, set[int]] = LRUCache()
        self.parse_cache: LRUCache[str, ParseTree] = LRUCache(limit=100)

    def get_saved_searches(self) -> SavedSearchQueries:
        return self.saved_searches

    def change_locations(self, newlocs: Collection[str]) -> None:
        if frozenset(newlocs) != frozenset(self.all_search_locations):
            self.clear_caches()
            self.parse_cache.clear()
        self.all_search_locations = newlocs

    def update_or_clear(self, dbcache: Cache, book_ids: Collection[int] | None = None) -> None:
        if book_ids and (len(book_ids) * len(self.cache)) <= self.MAX_CACHE_UPDATE:
            self.update_caches(dbcache, book_ids)
        else:
            self.clear_caches()

    def clear_caches(self) -> None:
        self.cache.clear()

    def update_caches(self, dbcache: Cache, book_ids: Iterable[int]) -> None:
        sqp = self.create_parser(dbcache)
        try:
            return self._update_caches(sqp, book_ids)
        finally:
            sqp.dbcache = sqp.lookup_saved_search = None  # ty: ignore[invalid-assignment]

    def discard_books(self, book_ids: Iterable[int]) -> None:
        book_ids = set(book_ids)
        for query, result in self.cache:
            result.difference_update(book_ids)

    def _update_caches(self, sqp: Parser, book_ids: Iterable[int]) -> None:
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

    def create_parser(self, dbcache: Cache, virtual_fields: dict[str, VirtualField] | None = None, allow_templates: bool = True) -> Parser:
        return Parser(
            dbcache,
            set(),
            cast('dict[str, list[str]]', dbcache._pref('grouped_search_terms')),
            self.date_search,
            self.num_search,
            self.bool_search,
            self.keypair_search,
            prefs['limit_search_columns'],
            prefs['limit_search_columns_to'],
            self.all_search_locations,
            virtual_fields,
            self.saved_searches.lookup,
            self.parse_cache,
            allow_templates=allow_templates,
        )

    def __call__(
        self,
        dbcache: Cache,
        query: str | bytes,
        search_restriction: str | bytes | None,
        virtual_fields: dict[str, VirtualField] | None = None,
        book_ids: set[int] | None = None,
        allow_templates: bool = True,
    ) -> set[int]:
        """
        Return the set of ids of all records that match the specified
        query and restriction
        """
        # We construct a new parser instance per search as the parse is not
        # thread safe.
        sqp = self.create_parser(dbcache, virtual_fields, allow_templates)
        try:
            return self._do_search(sqp, query, search_restriction, dbcache, book_ids=book_ids)
        finally:
            sqp.dbcache = sqp.lookup_saved_search = None  # ty: ignore[invalid-assignment]

    def query_uses_templates(self, dbcache: Cache, query: str) -> bool:
        """Return True if the query, or any saved search or grouped search term it
        uses, contains a template search. The query is not evaluated, so this works
        regardless of which books match. Raises ParseException if the query, or
        a saved search it uses, cannot be parsed."""
        sqp = self.create_parser(dbcache)
        try:
            fm = dbcache.field_metadata
            for location, _query in sqp.get_queried_fields(query):
                # Resolve the location as Parser.get_matches() does
                if len(location) > 2 and location.startswith('@') and location[1:] in sqp.grouped_search_terms:
                    location = location[1:]
                key = fm.search_term_to_field_key(icu_lower(location.strip()))
                for loc in key if isinstance(key, list) else (key,):
                    if fm.search_term_to_field_key(icu_lower(loc.strip())) == 'template':
                        return True
            return False
        finally:
            sqp.dbcache = sqp.lookup_saved_search = None  # ty: ignore[invalid-assignment]

    def query_is_cacheable(self, sqp: Parser, dbcache: Cache, query: str) -> bool:
        if query:
            for name, value in sqp.get_queried_fields(query):
                if name == 'template':
                    return False
                elif name in dbcache.field_metadata.all_field_keys():
                    fm = dbcache.field_metadata[name]
                    if fm['datatype'] == 'datetime':
                        return False
                    if fm['datatype'] == 'composite':
                        if fm.get('display', {}).get('composite_sort', '') == 'date':
                            return False
        return True

    def _do_search(self, sqp: Parser, query: str | bytes, search_restriction: str | bytes | None, dbcache: Cache, book_ids: set[int] | None = None) -> set[int]:
        """Do the search, caching the results. Results are cached only if the
        search is on the full library and no virtual field is searched on"""
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
