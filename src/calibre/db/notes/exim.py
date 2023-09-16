#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

import os
import shutil
from html5_parser import parse
from lxml import html
from urllib.parse import urlparse

from calibre.ebooks.chardet import xml_to_unicode
from calibre.utils.cleantext import clean_xml_chars
from calibre.utils.filenames import get_long_path_name, make_long_path_useable
from calibre.utils.html2text import html2text

from .connect import DOC_NAME, RESOURCE_URL_SCHEME


def parse_html(raw):
    try:
        return parse(raw, maybe_xhtml=False, sanitize_names=True)
    except Exception:
        return parse(clean_xml_chars(raw), maybe_xhtml=False, sanitize_names=True)


def export_note(note_data: dict, resources: dict[str, tuple[str, str]], dest_dir: str) -> str:
    for rhash, (path, name) in resources.items():
        d = os.path.join(dest_dir, name)
        shutil.copy2(path, d)
    root = parse_html(note_data['doc'])
    for img in root.xpath('//img[@src]'):
        try:
            purl = urlparse(img.get('src'))
        except Exception:
            continue
        if purl.scheme == RESOURCE_URL_SCHEME:
            rhash = f'{purl.hostname}:{purl.path[1:]}'
            x = resources.get(rhash)
            if x is not None:
                img.set('src', x[1])

    shtml = html.tostring(root, encoding='utf-8')
    with open(os.path.join(dest_dir, DOC_NAME), 'wb') as f:
        f.write(shtml)
    os.utime(f.name, times=(note_data['ctime'], note_data['mtime']))
    return DOC_NAME


def import_note(path_to_html_file: str, add_resource) -> dict:
    path_to_html_file = path_to_html_file
    with open(make_long_path_useable(path_to_html_file), 'rb') as f:
        raw = f.read()
    shtml = xml_to_unicode(raw, strip_encoding_pats=True, assume_utf8=True)[0]
    basedir = os.path.dirname(os.path.abspath(path_to_html_file))
    basedir = os.path.normcase(get_long_path_name(basedir) + os.sep)
    root = parse_html(shtml)
    resources = set()
    for img in root.xpath('//img[@src]'):
        src = img.attrib.pop('src')
        img.set('pre-import-src', src)
        try:
            purl = urlparse(img.get('src'))
        except Exception:
            continue
        if purl.scheme in ('', 'file'):
            path = purl.path
            if not os.path.isabs(path):
                path = os.path.join(basedir, path)
            q = os.path.normcase(get_long_path_name(os.path.abspath(path)))
            if q.startswith(basedir):
                rhash = add_resource(make_long_path_useable(path), os.path.basename(path))
                scheme, digest = rhash.split(':', 1)
                img.set('src', f'{RESOURCE_URL_SCHEME}://{scheme}/{digest}')
                resources.add(rhash)
    shtml = html.tostring(root, encoding='unicode')
    return shtml, html2text(shtml, default_image_alt=' '), resources
