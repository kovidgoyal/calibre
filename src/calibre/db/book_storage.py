#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# Per book persistent key/value storage used to implement localStorage for
# scripts inside books in the viewers. An entry is a dict of the form:
# {'timestamp': seconds since epoch, 'data': {key: value}} where keys and
# values are strings. When merging entries from different sources, the entry
# with the newest timestamp wins. Clearing the storage is represented by an
# entry with empty data, so that the clear propagates when syncing.

import time
from typing import TypedDict

# Maximum size of the stored data, in UTF-16 code units, same as the
# implementation in read_book.book_storage
MAX_BOOK_STORAGE_SIZE = 1024 * 1024


class BookStorageEntry(TypedDict):
    timestamp: float
    data: dict[str, str]


class InvalidBookStorage(ValueError):
    pass


def utf16_length(text: str) -> int:
    return len(text.encode('utf-16-le')) // 2


def book_storage_size(data: dict[str, str]) -> int:
    return sum(utf16_length(k) + utf16_length(v) for k, v in data.items())


def new_book_storage_entry(data: dict[str, str] | None = None, timestamp: float | None = None) -> BookStorageEntry:
    return {'timestamp': time.time() if timestamp is None else float(timestamp), 'data': dict(data or {})}


def validate_book_storage(entry: object) -> BookStorageEntry:
    """
    Check that entry is a valid book storage entry, returning a normalized
    copy. Raises InvalidBookStorage if it is not.
    """
    if not isinstance(entry, dict):
        raise InvalidBookStorage('Book storage must be an object')
    timestamp = entry.get('timestamp')
    if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or timestamp < 0:
        raise InvalidBookStorage('Book storage timestamp must be a non-negative number')
    data = entry.get('data')
    if not isinstance(data, dict):
        raise InvalidBookStorage('Book storage data must be an object')
    for k, v in data.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise InvalidBookStorage('Book storage keys and values must be strings')
    if book_storage_size(data) > MAX_BOOK_STORAGE_SIZE:
        raise InvalidBookStorage(f'Book storage data is larger than the maximum allowed size of {MAX_BOOK_STORAGE_SIZE}')
    return new_book_storage_entry(data, timestamp)


def newest_book_storage(*entries: BookStorageEntry | None) -> BookStorageEntry | None:
    "Return the entry with the newest timestamp, ignoring None entries. On ties the earliest entry wins."
    ans = None
    for entry in entries:
        if entry is not None and (ans is None or entry['timestamp'] > ans['timestamp']):
            ans = entry
    return ans
