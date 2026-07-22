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
