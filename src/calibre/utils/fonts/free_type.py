#!/usr/bin/env python
# License: GPLv3 Copyright: 2012, Kovid Goyal <kovid at kovidgoyal.net>

import threading
from collections.abc import Callable, Iterator
from functools import wraps
from typing import TYPE_CHECKING, Concatenate

from calibre_extensions.freetype import FreeType as _FreeType

if TYPE_CHECKING:
    from calibre_extensions.freetype import Face as _Face


class ThreadingViolation(Exception):
    def __init__(self) -> None:
        Exception.__init__(
            self,
            'You cannot use the freetype plugin from a thread other than the  thread in which startup() was called',
        )


def same_thread[S: Face | FreeType, **P, R](func: Callable[Concatenate[S, P], R]) -> Callable[Concatenate[S, P], R]:
    @wraps(func)
    def check_thread(self: S, *args: P.args, **kwargs: P.kwargs) -> R:
        if self.start_thread is not threading.current_thread():
            raise ThreadingViolation()
        return func(self, *args, **kwargs)

    return check_thread


class Face:
    def __init__(self, face: _Face) -> None:
        self.start_thread = threading.current_thread()
        self.face = face
        for x in ('family_name', 'style_name'):
            # The extension decodes the name as UTF-8 and raises if it is invalid
            try:
                val = getattr(self.face, x)
            except UnicodeDecodeError as e:
                val = repr(e.object)
            setattr(self, x, val)

    @same_thread
    def supports_text(self, text: str, has_non_printable_chars: bool = True) -> bool:
        """
        Returns True if all the characters in text have glyphs in this font.
        """
        if not isinstance(text, str):
            raise TypeError(f'{text!r} is not a unicode object')
        if has_non_printable_chars:
            from calibre.utils.fonts.utils import get_printable_characters

            text = get_printable_characters(text)
        chars = tuple(frozenset(map(ord, text)))
        return self.face.supports_text(chars)

    @same_thread
    def glyph_ids(self, text: str) -> Iterator[int]:
        if not isinstance(text, str):
            raise TypeError(f'{text!r} is not a unicode object')
        for char in text:
            yield self.face.glyph_id(ord(char))


class FreeType:
    def __init__(self) -> None:
        self.start_thread = threading.current_thread()
        self.ft = _FreeType()

    @same_thread
    def load_font(self, data: bytes) -> Face:
        return Face(self.ft.load_font(data))
