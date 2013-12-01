#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.utils.config import JSONConfig
tprefs = JSONConfig('tweak_book_gui')

tprefs.defaults['editor_theme'] = None
tprefs.defaults['editor_font_family'] = None
tprefs.defaults['editor_font_size'] = 12
tprefs.defaults['editor_line_wrap'] = True
tprefs.defaults['editor_tab_stop_width'] = 2
tprefs.defaults['preview_refresh_time'] = 2
tprefs.defaults['choose_tweak_fmt'] = True
tprefs.defaults['tweak_fmt_order'] = ['EPUB', 'AZW3']

_current_container = None

def current_container():
    return _current_container

def set_current_container(container):
    global _current_container
    _current_container = container

def elided_text(font, text, width=200, mode=None):
    from PyQt4.Qt import QFontMetrics, Qt
    if mode is None:
        mode = Qt.ElideMiddle
    fm = QFontMetrics(font)
    return unicode(fm.elidedText(text, mode, int(width)))

class NonReplaceDict(dict):

    def __setitem__(self, k, v):
        if k in self:
            raise ValueError('The key %s is already present' % k)
        dict.__setitem__(self, k, v)

actions = NonReplaceDict()
editors = NonReplaceDict()
