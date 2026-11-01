#!/usr/bin/env python
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from typing import IO, TYPE_CHECKING, NamedTuple, cast

from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.oeb.base import OPF
from calibre.ebooks.oeb.polish.utils import guess_type
from calibre.spell import parse_lang_code
from calibre.utils import StreamOrPath
from calibre.utils.cleantext import clean_xml_chars
from calibre.utils.localization import lang_as_iso639_1
from calibre.utils.xml_parse import safe_xml_fromstring

if TYPE_CHECKING:
    from collections.abc import Container, Iterable

    from _typeshed import SupportsRead
    from lxml.etree import _Element

    from calibre.spell import DictionaryLocale


class OPFVersion(NamedTuple):
    major: int
    minor: int
    patch: int


def parse_opf_version(raw: str | None) -> OPFVersion:
    parts = (raw or '').split('.')
    try:
        major = int(parts[0])
    except Exception:
        return OPFVersion(2, 0, 0)
    try:
        v = list(map(int, parts))  # parts == raw.split('.') as raw is non-empty here
    except Exception:
        v = [major, 0, 0]
    while len(v) < 3:
        v.append(0)
    v = v[:3]
    return OPFVersion(*v)


def parse_opf(stream_or_path: str | bytes | SupportsRead[bytes]) -> _Element:
    # StreamOrPath only needs the read() method of streams
    with StreamOrPath(cast('str | bytes | IO[bytes]', stream_or_path), 'rb') as stream:
        raw = stream.read()
    if not raw:
        raise ValueError('Empty file: ' + getattr(stream, 'name', 'stream'))
    raw, encoding = xml_to_unicode(raw, strip_encoding_pats=True, resolve_entities=True, assume_utf8=True)
    raw = raw[raw.find('<') :]
    root = safe_xml_fromstring(clean_xml_chars(raw))
    if root is None:
        raise ValueError('Not an OPF file')
    return root


def normalize_languages(opf_languages: Iterable[str], mi_languages: Iterable[str]) -> list[str]:
    "Preserve original country codes and use 2-letter lang codes where possible"

    def parse(x: str) -> DictionaryLocale | None:
        try:
            return parse_lang_code(x)
        except ValueError:
            return None

    opf_locales = filter(None, map(parse, opf_languages))
    cc_map = {c.langcode: c.countrycode for c in opf_locales}
    mi_locales = filter(None, map(parse, mi_languages))

    def norm(x: DictionaryLocale) -> str:
        lc = x.langcode
        cc = x.countrycode or cc_map.get(lc, None)
        lc = lang_as_iso639_1(lc) or lc
        if cc:
            lc += '-' + cc
        return lc

    return list(map(norm, mi_locales))


def ensure_unique(template: str, existing: Container[str]) -> str:
    b, e = template.rpartition('.')[::2]
    if b and e:
        e = '.' + e
    else:
        b, e = template, ''
    q = template
    c = 0
    while q in existing:
        c += 1
        q = f'{b}-{c}{e}'
    return q


def create_manifest_item(root: _Element, href_template: str, id_template: str, media_type: str | None = None) -> _Element | None:
    all_ids = frozenset(root.xpath('//*/@id'))
    all_hrefs = frozenset(root.xpath('//*/@href'))
    href = ensure_unique(href_template, all_hrefs)
    item_id = ensure_unique(id_template, all_ids)
    manifest = root.find(OPF('manifest'))
    if manifest is not None:
        i = manifest.makeelement(OPF('item'))
        i.set('href', href), i.set('id', item_id)
        i.set('media-type', media_type or guess_type(href_template))
        manifest.append(i)
        return i


def pretty_print_opf(root: _Element) -> None:
    from calibre.ebooks.oeb.polish.pretty import pretty_opf, pretty_xml_tree

    pretty_opf(root)
    pretty_xml_tree(root)
