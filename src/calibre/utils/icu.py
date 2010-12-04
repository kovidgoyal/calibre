#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial

from calibre.constants import plugins

_icu = _collator = None

_none = u''
_none2 = b''

def load_icu():
    global _icu
    if _icu is None:
        _icu = plugins['icu'][0]
        if _icu is None:
            print plugins['icu'][1]
        else:
            if not _icu.ok:
                print 'icu not ok'
                _icu = None
    return _icu

def load_collator():
    global _collator
    from calibre.utils.localization import get_lang
    if _collator is None:
        icu = load_icu()
        if icu is not None:
            _collator = icu.Collator(get_lang())
    return _collator


def py_sort_key(obj):
    if not obj:
        return _none
    return obj.lower()

def icu_sort_key(collator, obj):
    if not obj:
        return _none2
    return collator.sort_key(obj.lower())

load_icu()
load_collator()
sort_key = py_sort_key if _icu is None or _collator is None else \
        partial(icu_sort_key, _collator)

