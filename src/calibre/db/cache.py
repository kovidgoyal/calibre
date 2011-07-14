#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import wraps

from calibre.db.locking import create_locks
from calibre.db.fields import create_field

def api(f):
    f.is_cache_api = True
    return f

def read_api(f):
    f = api(f)
    f.is_read_api = True
    return f

def write_api(f):
    f = api(f)
    f.is_read_api = False
    return f

def wrap_simple(lock, func):
    @wraps(func)
    def ans(*args, **kwargs):
        with lock:
            return func(*args, **kwargs)
    return ans


class Cache(object):

    def __init__(self, backend):
        self.backend = backend
        self.fields = {}
        self.read_lock, self.write_lock = create_locks()

        # Implement locking for all simple read/write API methods
        # An unlocked version of the method is stored with the name starting
        # with a leading underscore. Use the unlocked versions when the lock
        # has already been acquired.
        for name in dir(self):
            func = getattr(self, name)
            ira = getattr(func, 'is_read_api', None)
            if ira is not None:
                # Save original function
                setattr(self, '_'+name, func)
                # Wrap it in a lock
                lock = self.read_lock if ira else self.write_lock
                setattr(self, name, wrap_simple(lock, func))

    # Cache Layer API {{{

    @api
    def init(self):
        '''
        Initialize this cache with data from the backend.
        '''
        with self.write_lock:
            self.backend.read_tables()

            for field, table in self.backend.tables.iteritems():
                self.fields[field] = create_field(field, table)

    @read_api
    def field_for(self, name, book_id, default_value=None):
        '''
        Return the value of the field ``name`` for the book identified by
        ``book_id``. If no such book exists or it has no defined value for the
        field ``name`` or no such field exists, then ``default_value`` is returned.

        The returned value for is_multiple fields are always tuples.
        '''
        try:
            return self.fields[name].for_book(book_id, default_value=default_value)
        except (KeyError, IndexError):
            return default_value

    @read_api
    def field_ids_for(self, name, book_id):
        '''
        Return the ids (as a tuple) for the values that the field ``name`` has on the book
        identified by ``book_id``. If there are no values, or no such book, or
        no such field, an empty tuple is returned.
        '''
        try:
            return self.fields[name].ids_for_book(book_id)
        except (KeyError, IndexError):
            return ()

    @read_api
    def books_for_field(self, name, item_id):
        '''
        Return all the books associated with the item identified by
        ``item_id``, where the item belongs to the field ``name``.

        Returned value is a tuple of book ids, or the empty tuple if the item
        or the field does not exist.
        '''
        try:
            return self.fields[name].books_for(item_id)
        except (KeyError, IndexError):
            return ()

    @read_api
    def all_book_ids(self):
        '''
        Frozen set of all known book ids.
        '''
        return frozenset(self.fields['uuid'].iter_book_ids())

    @read_api
    def all_field_ids(self, name):
        '''
        Frozen set of ids for all values in the field ``name``.
        '''
        return frozenset(iter(self.fields[name]))

    # }}}

# Testing {{{

def test(library_path):
    from calibre.db.backend import DB
    backend = DB(library_path)
    cache = Cache(backend)
    cache.init()
    print ('All book ids:', cache.all_book_ids())

if __name__ == '__main__':
    from calibre.utils.config import prefs
    test(prefs['library_path'])

# }}}
