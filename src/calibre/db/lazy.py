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
        return str(self._values)

    @resolved
    def __repr__(self):
        return repr(self._values)

    @resolved
    def __unicode__(self):
        return unicode(self._values)

    @resolved
    def __len__(self):
        return len(self._values)

    @resolved
    def __iter__(self):
        return iter(self._values)

    @resolved
    def __contains__(self, key):
        return key in self._values

    @resolved
    def __getitem__(self, fmt):
        return self._values[fmt]

    @resolved
    def __setitem__(self, key, val):
        self._values[key] = val

    @resolved
    def __delitem__(self, key):
        del self._values[key]

# }}}

class FormatMetadata(MutableBaseMixin, MutableMapping): # {{{

    def __init__(self, db, id_, formats):
        self._dbwref = weakref.ref(db)
        self._id = id_
        self._formats = formats

    def _resolve(self):
        db = self._dbwref()
        self._values = {}
        for f in self._formats:
            try:
                self._values[f] = db.format_metadata(self._id, f)
            except:
                pass

class FormatsList(MutableBaseMixin, MutableSequence):

    def __init__(self, formats, format_metadata):
        self._formats = formats
        self._format_metadata = format_metadata

    def _resolve(self):
        self._values = [f for f in self._formats if f in self._format_metadata]

    @resolved
    def insert(self, idx, val):
        self._values.insert(idx, val)

# }}}


