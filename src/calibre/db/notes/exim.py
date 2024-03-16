#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

import base64
import os
from html5_parser import parse
from lxml import html
from urllib.parse import unquote, urlparse

from calibre import guess_extension, guess_type
from calibre.db.constants import RESOURCE_URL_SCHEME
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.oeb.transforms.rasterize import data_url
from calibre.utils.cleantext import clean_xml_chars
from calibre.utils.filenames import get_long_path_name, make_long_path_useable
from calibre.utils.html2text import html2text


def parse_html(raw):
    try:
        return parse(raw, maybe_xhtml=False, sanitize_names=True)
    except Exception:
        return parse(clean_xml_chars(raw), maybe_xhtml=False, sanitize_names=True)


def export_note(note_doc: str, get_resource) -> str:
    root = parse_html(note_doc)
    return html.tostring(expand_note_resources(root, get_resource), encoding='unicode')


def expand_note_resources(root, get_resource):
    for img in root.xpath('//img[@src]'):
        img.attrib.pop('data-pre-import-src', None)
        try:
            purl = urlparse(img.get('src'))
        except Exception:
            continue
        if purl.scheme == RESOURCE_URL_SCHEME:
            rhash = f'{purl.hostname}:{purl.path[1:]}'
            x = get_resource(rhash)
            if x:
                img.set('src', data_url(guess_type(x['name'])[0], x['data']))
                img.set('data-filename', x['name'])
    return root


def import_note(shtml: str | bytes, basedir: str, add_resource) -> tuple[str, str, set[str]]:
    shtml = xml_to_unicode(shtml, strip_encoding_pats=True, assume_utf8=True)[0]
    basedir = os.path.normcase(get_long_path_name(os.path.abspath(basedir)) + os.sep)
    root = parse_html(shtml)
    resources = set()

    def ar(img, path_or_data, name):
        rhash = add_resource(path_or_data, name)
        scheme, digest = rhash.split(':', 1)
        img.set('src', f'{RESOURCE_URL_SCHEME}://{scheme}/{digest}')
        resources.add(rhash)

    for img in root.xpath('//img[@src]'):
        src = img.attrib.pop('src')
        img.set('data-pre-import-src', src)
        if src.startswith('data:'):
            d = src.split(':', 1)[-1]
            menc, payload = d.partition(',')[::2]
            mt, enc = menc.partition(';')[::2]
            if enc != 'base64':
                continue
            try:
                d = base64.standard_b64decode(payload)
            except Exception:
                continue
            ar(img, d, img.get('data-filename') or ('image' + guess_extension(mt, strict=False)))
            continue
        try:
            purl = urlparse(src)
        except Exception:
            continue
        if purl.scheme in ('', 'file'):
            path = unquote(purl.path)
            if not os.path.isabs(path):
                if not basedir:
                    continue
                path = os.path.join(basedir, path)
            q = os.path.normcase(get_long_path_name(os.path.abspath(path)))
            if q.startswith(basedir) and os.path.exists(make_long_path_useable(path)):
                ar(img, make_long_path_useable(path), os.path.basename(path))
    shtml = html.tostring(root, encoding='unicode')
    for img in root.xpath('//img[@src]'):
        del img.attrib['src']
    return shtml, html2text(shtml, default_image_alt=' '), resources
