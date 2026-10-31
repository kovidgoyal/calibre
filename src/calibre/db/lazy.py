#!/usr/bin/env python
# License: GPLv3 Copyright: 2012, Kovid Goyal <kovid@kovidgoyal.net>

import weakref
from collections.abc import MutableMapping, MutableSequence
from copy import deepcopy
from functools import wraps
from typing import TYPE_CHECKING, Any, NoReturn

from calibre.ebooks.metadata.book import STANDARD_METADATA_FIELDS
from calibre.ebooks.metadata.book.base import ALL_METADATA_FIELDS, NULL_VALUES, SIMPLE_GET, TOP_LEVEL_IDENTIFIERS, Metadata
from calibre.ebooks.metadata.book.formatter import SafeFormat
from calibre.utils.date import utcnow
from calibre.utils.localization import _

if TYPE_CHECKING:
    from collections.abc import Callable, Container, Iterable, Iterator
    from typing import Concatenate

    from calibre.db.cache import Cache
    from calibre.library.field_metadata import FieldMetadata
    from calibre.utils.formatter import TemplateCache

    # The weakref to the db is assumed to be alive while metadata is read from it
    type DBRef = Callable[[], Cache]
    type ValueCache = dict[str, object]
    type Getter = Callable[[DBRef, int, ValueCache], object]

# Lazy format metadata retrieval {{{
'''
Avoid doing stats on all files in a book when getting metadata for that book.
Speeds up calibre startup with large libraries/libraries on a network share,
with a composite custom column.
'''


def resolved[T: MutableBase, **P, R](f: Callable[Concatenate[T, P], R]) -> Callable[Concatenate[T, P], R]:
    @wraps(f)
    def wrapper(self: T, *args: P.args, **kwargs: P.kwargs) -> R:
        if getattr(self, '_must_resolve', True):
            self._resolve()
            self._must_resolve = False
        return f(self, *args, **kwargs)

    return wrapper


class MutableBase:
    _values: Any
    _must_resolve: bool

    if TYPE_CHECKING:
        # Implemented by the subclasses

        def _resolve(self) -> None: ...

    @resolved
    def __str__(self) -> str:
        return str(self._values)

    @resolved
    def __repr__(self) -> str:
        return repr(self._values)

    @resolved
    def __unicode__(self) -> str:
        return str(self._values)

    @resolved
    def __len__(self) -> int:
        return len(self._values)

    @resolved
    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    @resolved
    def __contains__(self, key: object) -> bool:
        return key in self._values

    @resolved
    def __getitem__(self, fmt: str | int) -> object:
        return self._values[fmt]

    @resolved
    def __setitem__(self, key: str | int, val: object) -> None:
        self._values[key] = val

    @resolved
    def __delitem__(self, key: str | int) -> None:
        del self._values[key]


class FormatMetadata(MutableBase, MutableMapping):
    def __init__(self, db: Cache, id_: int, formats: Iterable[str]) -> None:
        self._dbwref = weakref.ref(db)
        self._id = id_
        self._formats = formats

    def _resolve(self) -> None:
        db = self._dbwref()
        assert db is not None
        self._values = {}
        for f in self._formats:
            try:
                self._values[f] = db.format_metadata(self._id, f)
            except Exception:
                pass


class FormatsList(MutableBase, MutableSequence):
    def __init__(self, formats: Iterable[str], format_metadata: Container[str]) -> None:
        self._formats = formats
        self._format_metadata = format_metadata

    def _resolve(self) -> None:
        self._values = [f for f in self._formats if f in self._format_metadata]

    @resolved
    def insert(self, idx: int, val: str) -> None:
        self._values.insert(idx, val)


# }}}

# Lazy metadata getters {{{
ga = object.__getattribute__
sa = object.__setattr__


def simple_getter(field: str, default_value: object = None) -> Getter:
    def func(dbref: DBRef, book_id: int, cache: ValueCache) -> object:
        try:
            return cache[field]
        except KeyError:
            db = dbref()
            cache[field] = ret = db.field_for(field, book_id, default_value=default_value)
            return ret

    return func


def pp_getter(field: str, postprocess: Callable[[Iterable[str]], list[str]], default_value: object = None) -> Getter:
    def func(dbref: DBRef, book_id: int, cache: ValueCache) -> object:
        try:
            return cache[field]
        except KeyError:
            db = dbref()
            cache[field] = ret = postprocess(db.field_for(field, book_id, default_value=default_value))  # ty: ignore[invalid-argument-type]
            return ret

    return func


def adata_getter(field: str) -> Getter:
    def func(dbref: DBRef, book_id: int, cache: ValueCache) -> dict[str, str]:
        try:
            author_ids, adata = cache['adata']  # ty: ignore[not-iterable]
        except KeyError:
            db = dbref()
            with db.safe_read_lock:
                author_ids = db._field_ids_for('authors', book_id)
                adata = db._author_data(author_ids)
            cache['adata'] = (author_ids, adata)
        k = 'sort' if field == 'author_sort_map' else 'link'
        return {adata[i]['name']: adata[i][k] for i in author_ids}

    return func


def link_maps_getter(dbref: DBRef, book_id: int, cache: ValueCache) -> object:
    try:
        ans = cache['link_maps']
    except KeyError:
        db = dbref()
        ans = cache['link_maps'] = db.get_all_link_maps_for_book(book_id)
    return ans


def dt_getter(field: str) -> Getter:
    def func(dbref: DBRef, book_id: int, cache: ValueCache) -> object:
        try:
            return cache[field]
        except KeyError:
            db = dbref()
            cache[field] = ret = db.field_for(field, book_id, default_value=utcnow())
            return ret

    return func


def item_getter(field: str, default_value: object = None, key: int | str = 0) -> Getter:
    def func(dbref: DBRef, book_id: int, cache: ValueCache) -> object:
        try:
            ret = cache[field]
        except KeyError:
            db = dbref()
            ret = cache[field] = db.field_for(field, book_id, default_value=default_value)
        try:
            return ret[key]  # ty: ignore[not-subscriptable]
        except IndexError, KeyError:
            return default_value

    return func


def fmt_getter(field: str) -> Getter:
    def func(dbref: DBRef, book_id: int, cache: ValueCache) -> object:
        try:
            format_metadata = cache['format_metadata']
        except KeyError:
            db = dbref()
            format_metadata = {}
            for fmt in db.formats(book_id, verify_formats=False):
                m = db.format_metadata(book_id, fmt)
                if m:
                    format_metadata[fmt] = m
        if field == 'formats':
            return sorted(format_metadata) or None  # ty: ignore[invalid-argument-type]
        return format_metadata

    return func


def approx_fmts_getter(dbref: DBRef, book_id: int, cache: ValueCache) -> object:
    try:
        return cache['formats']
    except KeyError:
        db = dbref()
        cache['formats'] = ret = list(db.field_for('formats', book_id))
        return ret


def series_index_getter(field: str = 'series') -> Getter:
    def func(dbref: DBRef, book_id: int, cache: ValueCache) -> object:
        try:
            series = getters[field](dbref, book_id, cache)
        except KeyError:
            series = custom_getter(field, dbref, book_id, cache)
        if series:
            try:
                return cache[field + '_index']
            except KeyError:
                db = dbref()
                cache[field + '_index'] = ret = db.field_for(field + '_index', book_id, default_value=1.0)
                return ret

    return func


def has_cover_getter(dbref: DBRef, book_id: int, cache: ValueCache) -> object:
    try:
        return cache['has_cover']
    except KeyError:
        db = dbref()
        cache['has_cover'] = ret = _('Yes') if db.field_for('cover', book_id, default_value=False) else ''
        return ret


def fmt_custom[T](x: tuple[T, ...] | T) -> list[T] | T:
    return list(x) if isinstance(x, tuple) else x


def custom_getter(field: str, dbref: DBRef, book_id: int, cache: ValueCache) -> object:
    try:
        return cache[field]
    except KeyError:
        db = dbref()
        cache[field] = ret = fmt_custom(db.field_for(field, book_id))
        return ret


def composite_getter(
    mi: ProxyMetadata,
    field: str,
    dbref: DBRef,
    book_id: int,
    cache: ValueCache,
    formatter: SafeFormat,
    template_cache: TemplateCache,
) -> object:
    try:
        return cache[field]
    except KeyError:
        cache[field] = 'RECURSIVE_COMPOSITE FIELD (Metadata) ' + field
        try:
            db = dbref()
            with db.safe_read_lock:
                try:
                    fo = db.fields[field]
                except KeyError:
                    ret = cache[field] = _('Invalid field: %s') % field
                else:
                    ret = cache[field] = fo._render_composite_with_cache(book_id, mi, formatter, template_cache)
        except Exception:
            import traceback

            traceback.print_exc()
            return f'ERROR WHILE EVALUATING: {field}'
        return ret


def virtual_libraries_getter(dbref: DBRef, book_id: int, cache: ValueCache) -> object:
    """
    This method is deprecated because it doesn't (and can't) return virtual
    library names when the VL search references marked books. It is replaced
    by db.view.get_virtual_libraries_for_books()
    """
    try:
        return cache['virtual_libraries']
    except KeyError:
        db = dbref()
        vls = db.virtual_libraries_for_books((book_id,))[book_id]
        ret = cache['virtual_libraries'] = ', '.join(vls)
        return ret


def user_categories_getter(proxy_metadata: ProxyMetadata) -> object:
    cache = ga(proxy_metadata, '_cache')
    try:
        return cache['user_categories']
    except KeyError:
        db = ga(proxy_metadata, '_db')()
        book_id = ga(proxy_metadata, '_book_id')
        ret = cache['user_categories'] = db.user_categories_for_books((book_id,), {book_id: proxy_metadata})[book_id]
        return ret


getters: dict[str, Getter] = {
    'title': simple_getter('title', _('Unknown')),
    'title_sort': simple_getter('sort', _('Unknown')),
    'authors': pp_getter('authors', list, (_('Unknown'),)),
    'author_sort': simple_getter('author_sort', _('Unknown')),
    'uuid': simple_getter('uuid', 'dummy'),
    'book_size': simple_getter('size', 0),
    'pages': simple_getter('pages', 0),
    'ondevice_col': simple_getter('ondevice', ''),
    'languages': pp_getter('languages', list),
    'language': item_getter('languages', default_value=NULL_VALUES['language']),
    'db_approx_formats': approx_fmts_getter,
    'has_cover': has_cover_getter,
    'tags': pp_getter('tags', list, (_('Unknown'),)),
    'series_index': series_index_getter(),
    'application_id': lambda x, book_id, y: book_id,
    'id': lambda x, book_id, y: book_id,
    'virtual_libraries': virtual_libraries_getter,
    'link_maps': link_maps_getter,
}

for field in ('comments', 'publisher', 'identifiers', 'series', 'rating'):
    getters[field] = simple_getter(field)

for field in ('author_sort_map',):
    getters[field] = adata_getter(field)

for field in ('timestamp', 'pubdate', 'last_modified'):
    getters[field] = dt_getter(field)

for field in TOP_LEVEL_IDENTIFIERS:
    getters[field] = item_getter('identifiers', key=field)

for field in ('formats', 'format_metadata'):
    getters[field] = fmt_getter(field)
# }}}


class ProxyMetadata(Metadata):
    # Set with object.__setattr__ in __init__, they are not stored in _cache
    template_cache: TemplateCache
    formatter: SafeFormat

    def __init__(self, db: Cache, book_id: int, formatter: SafeFormat | None = None) -> None:
        sa(self, 'template_cache', db.formatter_template_cache)
        if formatter is None:
            formatter = SafeFormat()
            formatter.allow_python_templates = True
        sa(self, 'formatter', formatter)
        sa(self, '_db', weakref.ref(db))
        sa(self, '_book_id', book_id)
        sa(self, '_cache', {'cover_data': (None, None), 'device_collections': []})
        sa(self, '_user_metadata', db.field_metadata)

    def __getattribute__(self, field: str) -> object:
        getter = getters.get(field, None)
        if getter is not None:
            return getter(ga(self, '_db'), ga(self, '_book_id'), ga(self, '_cache'))
        if field in SIMPLE_GET:
            if field == 'user_categories':
                return user_categories_getter(self)
            return ga(self, '_cache').get(field, None)
        try:
            return ga(self, field)
        except AttributeError:
            pass
        um = ga(self, '_user_metadata')
        d = um.get(field, None)
        if d is not None:
            dt = d['datatype']
            if dt != 'composite':
                if field.endswith('_index') and dt == 'float':
                    return series_index_getter(field[:-6])(ga(self, '_db'), ga(self, '_book_id'), ga(self, '_cache'))
                return custom_getter(field, ga(self, '_db'), ga(self, '_book_id'), ga(self, '_cache'))
            return composite_getter(
                self,
                field,
                ga(self, '_db'),
                ga(self, '_book_id'),
                ga(self, '_cache'),
                ga(self, 'formatter'),
                ga(self, 'template_cache'),
            )

        try:
            return ga(self, '_cache')[field]
        except KeyError:
            raise AttributeError(f'Metadata object has no attribute named: {field!r}')

    def __setattr__(self, field: str, val: object, extra: object = None) -> None:
        cache = ga(self, '_cache')
        cache[field] = val
        if extra is not None:
            cache[field + '_index'] = val

    # Replacements (overrides) for methods in the Metadata base class.
    # ProxyMetadata cannot set attributes.

    def _unimplemented_exception(self, method: str, add_txt: bool) -> NoReturn:
        raise NotImplementedError(f"{method}() cannot be used in this context. {'ProxyMetadata is read only' if add_txt else ''}")

    # Metadata returns a seemingly arbitrary set of items. Rather than attempt
    # compatibility, flag __iter__ as unimplemented. This won't break anything
    # because the Metadata version raises AttributeError
    def __iter__(self) -> NoReturn:
        raise NotImplementedError('__iter__() cannot be used in this context. Use the explicit methods such as all_field_keys()')

    def has_key(self, key: str) -> bool:
        return key in STANDARD_METADATA_FIELDS or key in ga(self, '_user_metadata')

    def deepcopy(self, class_generator: Callable[[], Metadata] = lambda: Metadata(None)) -> None:
        self._unimplemented_exception('deepcopy', add_txt=False)

    def deepcopy_metadata(self) -> FieldMetadata:
        return deepcopy(ga(self, '_user_metadata'))

    # def get(self, field, default=None)

    def get_extra(self, field: str, default: object = None) -> object:
        um = ga(self, '_user_metadata')
        if field + '_index' in um:
            try:
                return getattr(self, field + '_index')
            except AttributeError:
                return default
        raise AttributeError('Metadata object has no attribute named: ' + repr(field))

    def set(self, *args: object, **kwargs: object) -> None:
        self._unimplemented_exception('set', add_txt=True)

    def get_identifiers(self) -> dict[str, str]:
        res = self.get('identifiers')
        return {} if res is None else res

    def set_identifiers(self, identifiers: dict[str, str]) -> None:
        self._unimplemented_exception('set_identifiers', add_txt=True)

    def set_identifier(self, typ: str, val: str) -> None:
        self._unimplemented_exception('set_identifier', add_txt=True)

    def has_identifier(self, typ: str) -> bool:
        return typ in self.get('identifiers', {})

    # def standard_field_keys(self)

    def custom_field_keys(self) -> Iterator[str]:
        um = ga(self, '_user_metadata')
        return iter(um.custom_field_keys())

    def all_field_keys(self) -> frozenset[str]:
        um = ga(self, '_user_metadata')
        return ALL_METADATA_FIELDS.union(frozenset(um.all_field_keys()))

    def all_non_none_fields(self) -> None:
        self._unimplemented_exception('all_non_none_fields', add_txt=False)

    # This version can return custom column metadata while the Metadata version
    # won't.
    def get_standard_metadata(self, field: str, make_copy: bool = False) -> dict[str, object] | None:
        field_metadata = ga(self, '_user_metadata')
        if field in field_metadata and field_metadata[field]['kind'] == 'field':
            if make_copy:
                return deepcopy(field_metadata[field])
            return field_metadata[field]
        return None

    # def get_all_standard_metadata(self, make_copy)

    def get_all_user_metadata(self, make_copy: bool) -> dict[str, dict[str, object]]:
        um = ga(self, '_user_metadata')
        if make_copy:
            res = {k: deepcopy(um[k]) for k in um.custom_field_keys()}
        else:
            res = {k: um[k] for k in um.custom_field_keys()}
        return res

    # The Metadata version of this method works only with custom field keys. It
    # isn't clear how this method differs from get_standard_metadata other than
    # it will return non-'field' metadata. Leave it in case someone depends on
    # that.
    def get_user_metadata(self, field: str, make_copy: bool = False) -> dict[str, object] | None:
        um = ga(self, '_user_metadata')
        try:
            ans = um[field]
        except KeyError:
            pass
        else:
            if make_copy:
                ans = deepcopy(ans)
            return ans

    def set_all_user_metadata(self, metadata: dict[str, dict[str, object]]) -> None:
        self._unimplemented_exception('set_all_user_metadata', add_txt=True)

    def set_user_metadata(self, field: str, metadata: dict[str, object]) -> None:
        self._unimplemented_exception('set_user_metadata', add_txt=True)

    def remove_stale_user_metadata(self, other_mi: Metadata) -> None:
        self._unimplemented_exception('remove_stale_user_metadata', add_txt=True)

    def template_to_attribute(self, other: Metadata, ops: Iterable[tuple[str, str]]) -> None:
        self._unimplemented_exception('template_to_attribute', add_txt=True)

    def smart_update(self, *args: object, **kwargs: object) -> None:
        self._unimplemented_exception('smart_update', add_txt=True)

    # The rest of the methods in Metadata can be used as is.

    @property
    def _proxy_metadata(self) -> ProxyMetadata:

        return self
