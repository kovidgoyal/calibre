#!/usr/bin/env python
# License: GPLv3 Copyright: 2010, Kovid Goyal <kovid at kovidgoyal.net>

import re
from collections.abc import Iterable
from html.entities import name2codepoint
from typing import Literal, overload

from calibre.constants import preferred_encoding
from calibre_extensions.speedup import clean_xml_chars as _ncxc


def native_clean_xml_chars(x: str | bytes) -> str:
    if isinstance(x, bytes):
        x = x.decode(preferred_encoding)
    return _ncxc(x)


@overload
def ascii_pat(for_binary: Literal[True]) -> re.Pattern[bytes]: ...
@overload
def ascii_pat(for_binary: Literal[False] = False) -> re.Pattern[str]: ...
def ascii_pat(for_binary: bool = False) -> re.Pattern[str] | re.Pattern[bytes]:
    attr = 'binary' if for_binary else 'text'
    ans = getattr(ascii_pat, attr, None)
    if ans is None:
        chars = set(range(32)) - {9, 10, 13}
        chars.add(127)
        pat = '|'.join(map(chr, chars))
        if for_binary:
            pat = pat.encode('ascii')
        ans = re.compile(pat)
        setattr(ascii_pat, attr, ans)
    return ans


@overload
def clean_ascii_chars(txt: bytes, charlist: Iterable[int] | None = None) -> bytes: ...
@overload
def clean_ascii_chars(txt: str | None, charlist: Iterable[int] | None = None) -> str: ...
def clean_ascii_chars(txt: str | bytes | None, charlist: Iterable[int] | None = None) -> str | bytes:
    r"""
    Remove ASCII control chars.
    This is all control chars except \t, \n and \r
    """
    if isinstance(txt, bytes):
        if not txt:
            return b''
        if charlist is None:
            return ascii_pat(True).sub(b'', txt)
        return re.compile('|'.join(map(chr, charlist)).encode('utf-8')).sub(b'', txt)
    else:
        if not txt:
            return ''
        if charlist is None:
            return ascii_pat(False).sub('', txt)
        return re.compile('|'.join(map(chr, charlist))).sub('', txt)


def allowed(x: str) -> bool:
    x = ord(x)  # ty: ignore[invalid-assignment]
    return (x != 127 and (31 < x < 0xD7FF or x in (9, 10, 13))) or (0xE000 < x < 0xFFFD) or (0x10000 < x < 0x10FFFF)  # ty: ignore[unsupported-operator]


def py_clean_xml_chars(unicode_string: str) -> str:
    return ''.join(filter(allowed, unicode_string))


clean_xml_chars = native_clean_xml_chars or py_clean_xml_chars


def test_clean_xml_chars() -> None:
    raw = 'asd\x02a\U00010437x\ud801b\udffe\ud802'
    if native_clean_xml_chars(raw) != 'asda\U00010437xb':
        raise ValueError(f'Failed to XML clean: {raw!r}')


# Fredrik Lundh: http://effbot.org/zone/re-sub.htm#unescape-html
# Removes HTML or XML character references and entities from a text string.
#
# @param text The HTML (or XML) source text.
# @return The plain text, as a Unicode string, if necessary.


def unescape(text: str, rm: bool = False, rchar: str = '') -> str:
    def fixup(m: re.Match[str], rm: bool = rm, rchar: str = rchar) -> str:
        text = m.group(0)
        if text[:2] == '&#':
            # character reference
            try:
                if text[:3] == '&#x':
                    return chr(int(text[3:-1], 16))
                else:
                    return chr(int(text[2:-1]))
            except ValueError:
                pass
        else:
            # named entity
            try:
                text = chr(name2codepoint[text[1:-1]])
            except KeyError:
                pass
        if rm:
            return rchar  # replace by char
        return text  # leave as is

    return re.sub(r'&#?\w+;', fixup, text)
