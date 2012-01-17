#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import weakref
from functools import wraps
from collections import MutableMapping, MutableSequence

def resolved(f):
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        if getattr(self, '_must_resolve', True):
            self._must_resolve = False
            self._resolve()
        return f(self, *args, **kwargs)
    return wrapper

class MutableBaseMixin(object): # {{{
    @resolved
    def __str__(self):
        return str(self.values)

    @resolved
    def __repr__(self):
        return repr(self.values)

    @resolved
    def __unicode__(self):
        return unicode(self.values)

    @resolved
    def __len__(self):
        return len(self.values)

    @resolved
    def __iter__(self):
        return iter(self.values)

    @resolved
    def __contains__(self, key):
        return key in self.values

    @resolved
    def __getitem__(self, fmt):
        return self.values[fmt]

    @resolved
    def __setitem__(self, key, val):
        self.values[key] = val

    @resolved
    def __delitem__(self, key):
        del self.values[key]

# }}}

class FormatMetadata(MutableBaseMixin, MutableMapping): # {{{

    def __init__(self, db, id_, formats):
        self.dbwref = weakref.ref(db)
        self.id_ = id_
        self.formats = formats
        self.values = {}

    def _resolve(self):
        db = self.dbwref()
        for f in self.formats:
            try:
                self.values[f] = db.format_metadata(self.id_, f)
            except:
                pass

class FormatsList(MutableBaseMixin, MutableSequence):

    def __init__(self, formats, format_metadata):
        self.formats = formats
        self.format_metadata = format_metadata
        self.values = []

    def _resolve(self):
        self.values = [f for f in self.formats if f in self.format_metadata]

    def insert(self, idx, val):
        self._resolve()
        self.values.insert(idx, val)

# }}}


