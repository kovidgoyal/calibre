#!/usr/bin/env python
# License: GPLv3 Copyright: 2011, Kovid Goyal <kovid@kovidgoyal.net>


class NoSuchFormat(ValueError):
    pass


class NoTracebackException(Exception):
    suppress_traceback: bool = True


class NoSuchBook(KeyError):
    def __init__(self, book_id):
        KeyError.__init__(self, f'No book with id: {book_id} in database')
        self.book_id = book_id


class BooksNotRemoved(Exception):
    """
    Raised by remove_books() when the files of some books could not be deleted
    or moved to the trash. Those books are left unchanged in the library, all
    the other books are removed.
    """

    def __init__(self, failures: dict[int, str], removed: tuple[int, ...]):
        msg = 'Failed to remove the books with ids: {}\n\n{}'.format(', '.join(map(str, failures)), '\n\n'.join(failures.values()))
        Exception.__init__(self, msg)
        self.failures = failures  # map of book id to error details
        self.removed = removed
