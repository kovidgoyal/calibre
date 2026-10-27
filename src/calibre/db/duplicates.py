#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

# Find groups of duplicate books in the library, using the same title and
# author matching as the check for duplicates when adding books

from collections import defaultdict
from collections.abc import Iterable
from typing import TYPE_CHECKING

from calibre.db.utils import fuzzy_title
from calibre.ebooks.metadata import normalize_isbn
from calibre.utils.icu import lower as icu_lower
from calibre.utils.icu import sort_key
from calibre.utils.localization import canonicalize_lang

if TYPE_CHECKING:
    from calibre.db.cache import Cache


def title_author_key(title: str, authors: Iterable[str]) -> tuple[str, tuple[str, ...]]:
    return fuzzy_title(title or ''), tuple(sorted({icu_lower(a.strip()) for a in authors if a.strip()}))


def book_languages(languages: Iterable[str]) -> tuple[str, ...]:
    return tuple(x for x in map(canonicalize_lang, languages or ()) if x and x != 'und')


def split_by_language(book_ids: list[int], lang_map: dict[int, tuple[str, ...]]) -> list[list[int]]:
    # Books in different languages are not duplicates. Books without a
    # language are put with the books that have one, when there is only one
    # language, as for the check when adding books.
    by_lang = defaultdict(list)
    for book_id in book_ids:
        by_lang[lang_map.get(book_id, ())].append(book_id)
    unknown = by_lang.pop((), [])
    if len(by_lang) == 1:
        by_lang[next(iter(by_lang))].extend(unknown)
    elif unknown:
        by_lang[()] = unknown
    return list(by_lang.values())


def normalize_identifier(typ: str, val: str) -> str:
    val = (val or '').strip()
    if typ == 'isbn':
        return normalize_isbn(val.replace(' ', '').replace('-', ''))
    return icu_lower(val)


def find_duplicates(
    db: Cache, book_ids: Iterable[int] | None = None, identifier: str | None = None, different_languages_are_different: bool = True
) -> list[tuple[int, ...]]:
    """
    Return groups of duplicate books, each a tuple of book ids sorted by id.
    Books are duplicates when they have the same (fuzzy matched) title and
    the same authors or, if ``identifier`` is specified, the same value for
    that identifier type, for example: isbn. The groups are sorted by title sort.
    """
    book_ids = db.all_book_ids() if book_ids is None else frozenset(book_ids)
    titles = db.all_field_for('title', book_ids, default_value='')
    groups: dict[object, list[int]] = defaultdict(list)
    if identifier:
        identifier = icu_lower(identifier)
        for book_id, identifiers in db.all_field_for('identifiers', book_ids, default_value={}).items():
            val = normalize_identifier(identifier, (identifiers or {}).get(identifier, ''))
            if val:
                groups[val].append(book_id)
        candidates = list(groups.values())
    else:
        authors = db.all_field_for('authors', book_ids, default_value=())
        for book_id in book_ids:
            key = title_author_key(titles[book_id], authors[book_id])
            if key[0]:
                groups[key].append(book_id)
        candidates = [ids for ids in groups.values() if len(ids) > 1]
        if different_languages_are_different:
            lang_map = {book_id: book_languages(langs) for book_id, langs in db.all_field_for('languages', book_ids, default_value=()).items()}
            candidates = [g for ids in candidates for g in split_by_language(ids, lang_map)]
    ans = [tuple(sorted(ids)) for ids in candidates if len(ids) > 1]
    title_sorts = db.all_field_for('sort', {ids[0] for ids in ans}, default_value='')
    ans.sort(key=lambda ids: (sort_key(title_sorts[ids[0]]), ids))
    return ans


def identifier_types(db: Cache) -> list[str]:
    "All the identifier types used in the library, most common first"
    counts = defaultdict(int)
    for identifiers in db.all_field_for('identifiers', db.all_book_ids(), default_value={}).values():
        for typ in identifiers or ():
            counts[typ] += 1
    return sorted(counts, key=lambda typ: (-counts[typ], typ))
