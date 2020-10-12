#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from collections import namedtuple

from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.oeb.base import OPF
from calibre.ebooks.oeb.polish.utils import guess_type
from calibre.spell import parse_lang_code
from calibre.utils.cleantext import clean_xml_chars
from calibre.utils.localization import lang_as_iso639_1
from calibre.utils.xml_parse import safe_xml_fromstring
from polyglot.builtins import filter, map

OPFVersion = namedtuple('OPFVersion', 'major minor patch')


def parse_opf_version(raw):
    parts = (raw or '').split('.')
    try:
        major = int(parts[0])
    except Exception:
        return OPFVersion(2, 0, 0)
    try:
        v = list(map(int, raw.split('.')))
    except Exception:
        v = [major, 0, 0]
    while len(v) < 3:
        v.append(0)
    v = v[:3]
    return OPFVersion(*v)


def parse_opf(stream_or_path):
    stream = stream_or_path
    if not hasattr(stream, 'read'):
        stream = open(stream, 'rb')
    raw = stream.read()
    if not raw:
        raise ValueError('Empty file: '+getattr(stream, 'name', 'stream'))
    raw, encoding = xml_to_unicode(raw, strip_encoding_pats=True, resolve_entities=True, assume_utf8=True)
    raw = raw[raw.find('<'):]
    root = safe_xml_fromstring(clean_xml_chars(raw))
    if root is None:
        raise ValueError('Not an OPF file')
    return root


def normalize_languages(opf_languages, mi_languages):
    ' Preserve original country codes and use 2-letter lang codes where possible '
    def parse(x):
        try:
            return parse_lang_code(x)
        except ValueError:
            return None
    opf_languages = filter(None, map(parse, opf_languages))
    cc_map = {c.langcode:c.countrycode for c in opf_languages}
    mi_languages = filter(None, map(parse, mi_languages))

    def norm(x):
        lc = x.langcode
        cc = x.countrycode or cc_map.get(lc, None)
        lc = lang_as_iso639_1(lc) or lc
        if cc:
            lc += '-' + cc
        return lc
    return list(map(norm, mi_languages))


def ensure_unique(template, existing):
    b, e = template.rpartition('.')[::2]
    if b and e:
        e = '.' + e
    else:
        b, e = template, ''
    q = template
    c = 0
    while q in existing:
        c += 1
        q = '%s-%d%s' % (b, c, e)
    return q


def create_manifest_item(root, href_template, id_template, media_type=None):
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


def pretty_print_opf(root):
    from calibre.ebooks.oeb.polish.pretty import pretty_opf, pretty_xml_tree
    pretty_opf(root)
    pretty_xml_tree(root)
