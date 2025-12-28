#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import NamedTuple

COVER_FILE_NAME = 'cover.jpg'
METADATA_FILE_NAME = 'metadata.opf'
DEFAULT_TRASH_EXPIRY_TIME_SECONDS = 14 * 86400
TRASH_DIR_NAME = '.caltrash'
NOTES_DIR_NAME = '.calnotes'
NOTES_DB_NAME = 'notes.db'
DATA_DIR_NAME = 'data'
DATA_FILE_PATTERN = f'{DATA_DIR_NAME}/**/*'
BOOK_ID_PATH_TEMPLATE = ' ({})'
RESOURCE_URL_SCHEME = 'calres'
TEMPLATE_ICON_INDICATOR = ' template '  # Item values cannot start or end with space
NO_SEARCH_LINK = '__no_link__'


@dataclass
class TrashEntry:
    book_id: int
    title: str
    author: str
    cover_path: str
    mtime: float
    formats: Sequence[str] = ()


class Pages(NamedTuple):
    pages: int
    algorithm: int
    format: str
    format_size: int
    timestamp: datetime
