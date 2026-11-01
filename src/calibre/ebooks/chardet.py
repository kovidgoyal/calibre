#!/usr/bin/env python
# License: GPLv3 Copyright: 2009, Kovid Goyal <kovid@kovidgoyal.net>

import codecs
import re
import sys
from typing import TYPE_CHECKING, Literal, TypedDict, overload

from calibre import xml_replace_entities

if TYPE_CHECKING:
    from collections.abc import Iterator


class ChardetResult(TypedDict):
    encoding: str
    confidence: int


_encoding_pats = (
    # XML declaration
    r'<\?[^<>]+encoding\s*=\s*[\'"](.*?)[\'"][^<>]*>',
    # HTML 5 charset
    r'''<meta\s+charset=['"]([-_a-z0-9]+)['"][^<>]*>(?:\s*</meta>){0,1}''',
    # HTML 4 Pragma directive
    r'''<meta\s+?[^<>]*?content\s*=\s*['"][^'"]*?charset=([-_a-z0-9]+)[^'"]*?['"][^<>]*>(?:\s*</meta>){0,1}''',
)
substitute_entities = substitute_entites = xml_replace_entities  # for plugins that might use this


@overload
def compile_pats(binary: Literal[False]) -> Iterator[re.Pattern[str]]: ...
@overload
def compile_pats(binary: Literal[True]) -> Iterator[re.Pattern[bytes]]: ...
@overload
def compile_pats(binary: bool) -> Iterator[re.Pattern[str]] | Iterator[re.Pattern[bytes]]: ...
def compile_pats(binary: bool) -> Iterator[re.Pattern[str]] | Iterator[re.Pattern[bytes]]:
    for raw in _encoding_pats:
        if binary:
            raw = raw.encode('ascii')
        yield re.compile(raw, flags=re.IGNORECASE)


class LazyEncodingPats:
    @overload
    def __call__(self, binary: Literal[False] = False) -> Iterator[re.Pattern[str]]: ...
    @overload
    def __call__(self, binary: Literal[True]) -> Iterator[re.Pattern[bytes]]: ...
    @overload
    def __call__(self, binary: bool) -> Iterator[re.Pattern[str]] | Iterator[re.Pattern[bytes]]: ...
    def __call__(self, binary: bool = False) -> Iterator[re.Pattern[str]] | Iterator[re.Pattern[bytes]]:
        attr = 'binary_pats' if binary else 'unicode_pats'
        pats = getattr(self, attr, None)
        if pats is None:
            pats = tuple(compile_pats(binary))
            setattr(self, attr, pats)
        yield from pats


lazy_encoding_pats = LazyEncodingPats()


def strip_encoding_declarations[T: (str, bytes)](raw: T, limit: int = 50 * 1024, preserve_newlines: bool = False) -> T:
    prefix = raw[:limit]
    suffix = raw[limit:]
    is_binary = isinstance(raw, bytes)
    if preserve_newlines:
        if is_binary:

            def sub(m: re.Match[bytes]) -> bytes:
                return b'\n' * m.group().count(b'\n')

        else:

            def sub(m: re.Match[str]) -> str:
                return '\n' * m.group().count('\n')

    else:
        sub = b'' if is_binary else ''
    for pat in lazy_encoding_pats(is_binary):
        prefix = pat.sub(sub, prefix)  # ty: ignore[no-matching-overload] pat, sub and prefix are all str or all bytes
    raw = prefix + suffix
    return raw


def replace_encoding_declarations[T: (str, bytes)](raw: T, enc: str | bytes = 'utf-8', limit: int = 50 * 1024) -> tuple[T, bool]:
    prefix = raw[:limit]
    suffix = raw[limit:]
    changed = [False]
    is_binary = isinstance(raw, bytes)
    if is_binary:
        if not isinstance(enc, bytes):
            enc = enc.encode('ascii')
    elif isinstance(enc, bytes):
        enc = enc.decode('ascii')

    def sub(m: re.Match[str] | re.Match[bytes]) -> str | bytes:
        ans = m.group()
        if m.group(1).lower() != enc.lower():
            changed[0] = True
            start, end = m.start(1) - m.start(0), m.end(1) - m.end(0)
            ans = ans[:start] + enc + ans[end:]  # ty: ignore[unsupported-operator] ans and enc are both str or both bytes
        return ans

    for pat in lazy_encoding_pats(is_binary):
        prefix = pat.sub(sub, prefix)  # ty: ignore[no-matching-overload] pat, sub and prefix are all str or all bytes
    raw = prefix + suffix
    return raw, changed[0]


def find_declared_encoding(raw: str | bytes, limit: int = 50 * 1024) -> str | None:
    prefix = raw[:limit]
    is_binary = isinstance(raw, bytes)
    for pat in lazy_encoding_pats(is_binary):
        m = pat.search(prefix)  # ty: ignore[no-matching-overload] pat and prefix are both str or both bytes
        if m is not None:
            ans = m.group(1)
            if is_binary:
                ans = ans.decode('ascii', 'replace')
            return ans


_CHARSET_ALIASES = {'macintosh': 'mac-roman', 'x-sjis': 'shift-jis', 'mac-centraleurope': 'cp1250'}


def detect(bytestring: str | bytes) -> ChardetResult:
    if isinstance(bytestring, str):
        bytestring = bytestring.encode('utf-8', 'replace')
    from calibre_extensions.uchardet import detect as implementation

    enc = implementation(bytestring).lower()
    enc = _CHARSET_ALIASES.get(enc, enc)
    return {'encoding': enc, 'confidence': 1 if enc else 0}


def force_encoding(raw: bytes, verbose: int, assume_utf8: bool = False) -> str:
    from calibre.constants import preferred_encoding

    try:
        chardet = detect(raw[: 1024 * 50])
    except Exception:
        chardet = ChardetResult(encoding=preferred_encoding, confidence=0)
    encoding = chardet['encoding']
    if chardet['confidence'] < 1:
        if verbose:
            print(
                f'WARNING: Encoding detection confidence for {chardet["encoding"]} is {chardet["confidence"]}',
                file=sys.stderr,
            )
        if assume_utf8:
            encoding = 'utf-8'
    if not encoding:
        encoding = preferred_encoding
    encoding = encoding.lower()
    encoding = _CHARSET_ALIASES.get(encoding, encoding)
    if encoding == 'ascii':
        encoding = 'utf-8'
    return encoding


@overload
def detect_xml_encoding(raw: str, verbose: int = False, assume_utf8: bool = False) -> tuple[str, None]: ...
@overload
def detect_xml_encoding(raw: bytes, verbose: int = False, assume_utf8: bool = False) -> tuple[bytes, str | None] | tuple[str, str]: ...
@overload
def detect_xml_encoding(raw: str | bytes, verbose: int = False, assume_utf8: bool = False) -> tuple[str | bytes, str | None]: ...
def detect_xml_encoding(raw: str | bytes, verbose: int = False, assume_utf8: bool = False) -> tuple[str | bytes, str | None]:
    if not raw or isinstance(raw, str):
        return raw, None
    for x in ('utf8', 'utf-16-le', 'utf-16-be'):
        bom = getattr(codecs, 'BOM_' + x.upper().replace('-16', '16').replace('-', '_'))
        if raw.startswith(bom):
            return raw[len(bom) :], x
    encoding = None
    for pat in lazy_encoding_pats(True):
        match = pat.search(raw)
        if match:
            encoding = match.group(1)
            encoding = encoding.decode('ascii', 'replace')
            break
    if encoding is None:
        if assume_utf8:
            try:
                return raw.decode('utf-8'), 'utf-8'
            except UnicodeDecodeError:
                pass
        encoding = force_encoding(raw, verbose, assume_utf8=assume_utf8)
    if encoding.lower().strip() == 'macintosh':
        encoding = 'mac-roman'
    if encoding.lower().replace('_', '-').strip() in (
        'gb2312',
        'chinese',
        'csiso58gb231280',
        'euc-cn',
        'euccn',
        'eucgb2312-cn',
        'gb2312-1980',
        'gb2312-80',
        'iso-ir-58',
    ):
        # Microsoft Word exports to HTML with encoding incorrectly set to
        # gb2312 instead of gbk. gbk is a superset of gb2312, anyway.
        encoding = 'gbk'
    try:
        codecs.lookup(encoding)
    except LookupError:
        encoding = 'utf-8'

    return raw, encoding


def xml_to_unicode(
    raw: str | bytes, verbose: int = False, strip_encoding_pats: bool = False, resolve_entities: bool = False, assume_utf8: bool = False
) -> tuple[str, str | None]:
    """
    Force conversion of byte string to unicode. Tries to look for XML/HTML
    encoding declaration first, if not found uses the chardet library and
    prints a warning if detection confidence is < 100%
    @return: (unicode, encoding used)
    """
    if not raw:
        return '', None
    raw, encoding = detect_xml_encoding(raw, verbose=verbose, assume_utf8=assume_utf8)
    if not isinstance(raw, str):
        assert encoding is not None  # always detected for non-empty bytes
        raw = raw.decode(encoding, 'replace')

    if strip_encoding_pats:
        raw = strip_encoding_declarations(raw)
    if resolve_entities:
        raw = xml_replace_entities(raw)

    return raw, encoding
