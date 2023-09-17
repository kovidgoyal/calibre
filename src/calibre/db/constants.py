#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

from dataclasses import dataclass
from typing import Sequence

COVER_FILE_NAME = 'cover.jpg'
METADATA_FILE_NAME = 'metadata.opf'
DEFAULT_TRASH_EXPIRY_TIME_SECONDS = 14 * 86400
TRASH_DIR_NAME =  '.caltrash'
NOTES_DIR_NAME = '.calnotes'
NOTES_DB_NAME = 'notes.db'
DATA_DIR_NAME = 'data'
DATA_FILE_PATTERN = f'{DATA_DIR_NAME}/**/*'
BOOK_ID_PATH_TEMPLATE = ' ({})'
RESOURCE_URL_SCHEME = 'calres'


@dataclass
class TrashEntry:
    book_id: int
    title: str
    author: str
    cover_path: str
    mtime: float
    formats: Sequence[str] = ()
