# License: GPLv3 Copyright: 2008, Kovid Goyal <kovid at kovidgoyal.net>

"""Code to manage ebook library"""

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from calibre.db.legacy import LibraryDatabase


def db(path: str | None = None, read_only: bool = False) -> LibraryDatabase:
    from calibre.db.legacy import LibraryDatabase
    from calibre.utils.config import prefs

    return LibraryDatabase(os.path.expanduser(path) if path else prefs['library_path'], read_only=read_only)


def generate_test_db(
    library_path: str,  # {{{
    num_of_records: int = 20000,
    num_of_authors: int = 6000,
    num_of_tags: int = 10000,
    tag_length: int = 7,
    author_length: int = 7,
    title_length: int = 10,
    max_authors: int = 10,
    max_tags: int = 10,
) -> None:
    import os
    import random
    import string
    import sys
    import time

    if not os.path.exists(library_path):
        os.makedirs(library_path)

    letters = string.ascii_letters

    def randstr(length: int) -> str:
        return ''.join(random.choice(letters) for i in range(length))

    all_tags = [randstr(tag_length) for j in range(num_of_tags)]
    print('Generated', num_of_tags, 'tags')
    all_authors = [randstr(author_length) for j in range(num_of_authors)]
    print('Generated', num_of_authors, 'authors')
    all_titles = [randstr(title_length) for j in range(num_of_records)]
    print('Generated', num_of_records, 'titles')

    testdb = db(library_path)

    print('Creating', num_of_records, 'records...')

    start = time.time()

    for i, title in enumerate(all_titles):
        print(i + 1, end=' ')
        sys.stdout.flush()
        authors = random.randint(1, max_authors)
        authors = [random.choice(all_authors) for i in range(authors)]
        tags = random.randint(0, max_tags)
        tags = [random.choice(all_tags) for i in range(tags)]
        from calibre.ebooks.metadata.book.base import Metadata

        mi = Metadata(title, authors)
        mi.tags = tags
        testdb.import_book(mi, [])

    t = time.time() - start
    print('\nGenerated', num_of_records, 'records in:', t, 'seconds')
    print('Time per record:', t / num_of_records)


# }}}


def current_library_path() -> str | None:
    from calibre.utils.config import prefs

    path = prefs['library_path']
    if path:
        path = path.replace('\\', '/')
        while path.endswith('/'):
            path = path[:-1]
        return path


def current_library_name() -> str | None:
    import posixpath

    path = current_library_path()
    if path:
        return posixpath.basename(path)
