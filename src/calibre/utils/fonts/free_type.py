#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import threading, unicodedata
from functools import wraps
from future_builtins import map

from calibre.constants import plugins

class ThreadingViolation(Exception):

    def __init__(self):
        Exception.__init__(self,
                'You cannot use the MTP driver from a thread other than the '
                ' thread in which startup() was called')

def get_printable_characters(text):
    return u''.join(x for x in unicodedata.normalize('NFC', text)
            if unicodedata.category(x)[0] not in {'C', 'Z', 'M'})

def same_thread(func):
    @wraps(func)
    def check_thread(self, *args, **kwargs):
        if self.start_thread is not threading.current_thread():
            raise ThreadingViolation()
        return func(self, *args, **kwargs)
    return check_thread

FreeTypeError = getattr(plugins['freetype'][0], 'FreeTypeError', Exception)

class Face(object):

    def __init__(self, face):
        self.start_thread = threading.current_thread()
        self.face = face
        for x in ('family_name', 'style_name'):
            val = getattr(self.face, x)
            try:
                val = val.decode('utf-8')
            except UnicodeDecodeError:
                val = repr(val).decode('utf-8')
            setattr(self, x, val)

    @same_thread
    def supports_text(self, text, has_non_printable_chars=True):
        '''
        Returns True if all the characters in text have glyphs in this font.
        '''
        if not isinstance(text, unicode):
            raise TypeError('%r is not a unicode object'%text)
        if has_non_printable_chars:
            text = get_printable_characters(text)
        chars = tuple(frozenset(map(ord, text)))
        return self.face.supports_text(chars)

class FreeType(object):

    def __init__(self):
        self.start_thread = threading.current_thread()
        ft, ft_err = plugins['freetype']
        if ft_err:
            raise RuntimeError('Failed to load FreeType module with error: %s'
                    % ft_err)
        self.ft = ft.FreeType()

    @same_thread
    def load_font(self, data):
        return Face(self.ft.load_font(data))

def test():
    data = P('fonts/calibreSymbols.otf', data=True)
    ft = FreeType()
    font = ft.load_font(data)
    if not font.supports_text('.\u2605★'):
        raise RuntimeError('Incorrectly returning that text is not supported')
    if font.supports_text('abc'):
        raise RuntimeError('Incorrectly claiming that text is supported')

def test_find_font():
    from calibre.utils.fonts import fontconfig
    abcd = '诶比西迪'
    family = fontconfig.find_font_for_text(abcd)[0]
    print ('Family for Chinese text:', family)
    family = fontconfig.find_font_for_text(abcd)[0]
    abcd = 'لوحة المفاتيح العربية'
    print ('Family for Arabic text:', family)


if __name__ == '__main__':
    test()
    test_find_font()

