#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


class NoSuchFormat(ValueError):
    pass


class NoSuchBook(KeyError):

    def __init__(self, book_id):
        KeyError.__init__(self, f'No book with id: {book_id} in database')
        self.book_id = book_id
