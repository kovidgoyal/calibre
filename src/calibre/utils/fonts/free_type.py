#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import threading
from functools import wraps

from calibre_extensions.freetype import FreeType as _FreeType
from polyglot.builtins import map, unicode_type


class ThreadingViolation(Exception):

    def __init__(self):
        Exception.__init__(self,
                'You cannot use the freetype plugin from a thread other than the '
                ' thread in which startup() was called')


def same_thread(func):
    @wraps(func)
    def check_thread(self, *args, **kwargs):
        if self.start_thread is not threading.current_thread():
            raise ThreadingViolation()
        return func(self, *args, **kwargs)
    return check_thread


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
        if not isinstance(text, unicode_type):
            raise TypeError('%r is not a unicode object'%text)
        if has_non_printable_chars:
            from calibre.utils.fonts.utils import get_printable_characters
            text = get_printable_characters(text)
        chars = tuple(frozenset(map(ord, text)))
        return self.face.supports_text(chars)

    @same_thread
    def glyph_ids(self, text):
        if not isinstance(text, unicode_type):
            raise TypeError('%r is not a unicode object'%text)
        for char in text:
            yield self.face.glyph_id(ord(char))


class FreeType(object):

    def __init__(self):
        self.start_thread = threading.current_thread()
        self.ft = _FreeType()

    @same_thread
    def load_font(self, data):
        return Face(self.ft.load_font(data))
