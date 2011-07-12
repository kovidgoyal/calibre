#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.db.locking import create_locks
from calibre.db.fields import create_field

class Cache(object):

    def __init__(self, backend):
        self.backend = backend
        self.fields = {}
        self.read_lock, self.write_lock = create_locks()

    # Cache Layer API {{{

    def init(self):
        with self.write_lock:
            self.backend.read_tables()

            for field, table in self.backend.tables.iteritems():
                self.fields[field] = create_field(field, table)

    # }}}

