#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>


import os
import re
import unicodedata

from calibre.customize.ui import plugin_for_input_format
from calibre.ebooks.oeb.base import XPNSMAP, barename
from calibre.ebooks.oeb.iterator.book import extract_book
from calibre.ebooks.oeb.polish.container import Container as ContainerBase
from calibre.ebooks.oeb.polish.utils import BLOCK_TAG_NAMES
from calibre.ptempfile import TemporaryDirectory
from calibre.utils.logging import default_log


class SimpleContainer(ContainerBase):

    tweak_mode = True


skipped_tags = frozenset({'style', 'title', 'script', 'head', 'img', 'svg', 'math'})


def tag_to_text(tag):
    if tag.text:
        yield tag.text
    for child in tag:
        q = barename(child.tag).lower() if isinstance(child.tag, str) else ''
        if not q or q in skipped_tags:
            if child.tail:
                yield child.tail
        else:
            if q in BLOCK_TAG_NAMES:
                yield '\n\n'
            yield from tag_to_text(child)
    if tag.tail:
        yield tag.tail


def html_to_text(root):
    pat = re.compile(r'\n{3,}')
    for body in root.xpath('h:body', namespaces=XPNSMAP):
        body.tail = ''
        yield pat.sub('\n\n', ''.join(tag_to_text(body)).strip())


def to_text(container, name):
    root = container.parsed(name)
    if hasattr(root, 'xpath'):
        yield from html_to_text(root)


def is_fmt_ok(input_fmt):
    input_fmt = input_fmt.upper()
    input_plugin = plugin_for_input_format(input_fmt)
    is_comic = bool(getattr(input_plugin, 'is_image_collection', False))
    if not input_plugin or is_comic:
        return False
    return input_plugin


def pdftotext(path):
    import subprocess

    from calibre.ebooks.pdf.pdftohtml import PDFTOTEXT, popen
    from calibre.utils.cleantext import clean_ascii_chars
    cmd = [PDFTOTEXT] + '-enc UTF-8 -nodiag -eol unix'.split() + [os.path.basename(path), '-']
    p = popen(cmd, cwd=os.path.dirname(path), stdout=subprocess.PIPE, stdin=subprocess.DEVNULL)
    raw = p.stdout.read()
    if p.wait() != 0:
        return ''
    return clean_ascii_chars(raw).decode('utf-8', 'replace')


def extract_text(pathtoebook):
    input_fmt = pathtoebook.rpartition('.')[-1].upper()
    ans = ''
    input_plugin = is_fmt_ok(input_fmt)
    if not input_plugin:
        return ans
    input_plugin = plugin_for_input_format(input_fmt)
    if input_fmt == 'PDF':
        ans = pdftotext(pathtoebook)
    else:
        with TemporaryDirectory() as tdir:
            texts = []
            book_fmt, opfpath, input_fmt = extract_book(pathtoebook, tdir, log=default_log)
            input_plugin = plugin_for_input_format(input_fmt)
            is_comic = bool(getattr(input_plugin, 'is_image_collection', False))
            if is_comic:
                return ''
            container = SimpleContainer(tdir, opfpath, default_log)
            for name, is_linear in container.spine_names:
                texts.extend(to_text(container, name))
            ans = '\n\n\n'.join(texts)
    return unicodedata.normalize('NFC', ans).replace('\u00ad', '')


def main(pathtoebook):
    text = extract_text(pathtoebook)
    with open(pathtoebook + '.txt', 'wb') as f:
        f.write(text.encode('utf-8'))
