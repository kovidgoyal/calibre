#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, os

from lxml import html
from lxml.html.builder import (
    HTML, HEAD, TITLE, BODY, LINK, META, P, SPAN, BR)

from calibre.ebooks.docx.container import DOCX, fromstring
from calibre.ebooks.docx.names import XPath, is_tag, barename, XML, STYLES
from calibre.ebooks.docx.styles import Styles
from calibre.utils.localization import canonicalize_lang, lang_as_iso639_1

class Text:

    def __init__(self, elem, attr, buf):
        self.elem, self.attr, self.buf = elem, attr, buf

    def add_elem(self, elem):
        setattr(self.elem, self.attr, ''.join(self.buf))
        self.elem, self.attr, self.buf = elem, 'tail', []

class Convert(object):

    def __init__(self, path_or_stream, dest_dir=None, log=None):
        self.docx = DOCX(path_or_stream, log=log)
        self.log = self.docx.log
        self.dest_dir = dest_dir or os.getcwdu()
        self.mi = self.docx.metadata
        self.body = BODY()
        self.styles = Styles()
        self.html = HTML(
            HEAD(
                META(charset='utf-8'),
                TITLE(self.mi.title or _('Unknown')),
                LINK(rel='stylesheet', type='text/css', href='docx.css'),
            ),
            self.body
        )
        self.html.text='\n\t'
        self.html[0].text='\n\t\t'
        self.html[0].tail='\n'
        for child in self.html[0]:
            child.tail = '\n\t\t'
        self.html[0][-1].tail = '\n\t'
        self.html[1].text = self.html[1].tail = '\n'
        lang = canonicalize_lang(self.mi.language)
        if lang and lang != 'und':
            lang = lang_as_iso639_1(lang)
            if lang:
                self.html.set('lang', lang)

    def __call__(self):
        doc = self.docx.document
        relationships_by_id, relationships_by_type = self.docx.document_relationships
        self.read_styles(relationships_by_type)
        for top_level in XPath('/w:document/w:body/*')(doc):
            if is_tag(top_level, 'w:p'):
                p = self.convert_p(top_level)
                self.body.append(p)
            elif is_tag(top_level, 'w:tbl'):
                pass  # TODO: tables
            elif is_tag(top_level, 'w:sectPr'):
                pass  # TODO: Last section properties
            else:
                self.log.debug('Unknown top-level tag: %s, ignoring' % barename(top_level.tag))
        if len(self.body) > 0:
            self.body.text = '\n\t'
            for child in self.body:
                child.tail = '\n\t'
            self.body[-1].tail = '\n'
        self.write()

    def read_styles(self, relationships_by_type):
        sname = relationships_by_type.get(STYLES, None)
        if sname is None:
            name = self.docx.document_name.split('/')
            name[-1] = 'styles.xml'
            if self.docx.exists(name):
                sname = name
        if sname is not None:
            try:
                raw = self.docx.read(sname)
            except KeyError:
                self.log.warn('Styles %s do not exist' % sname)
            else:
                self.styles(fromstring(raw))

    def write(self):
        raw = html.tostring(self.html, encoding='utf-8', doctype='<!DOCTYPE html>')
        with open(os.path.join(self.dest_dir, 'index.html'), 'wb') as f:
            f.write(raw)

    def convert_p(self, p):
        dest = P()
        for run in XPath('descendant::w:r')(p):
            span = self.convert_run(run)
            dest.append(span)

        return dest

    def convert_run(self, run):
        ans = SPAN()
        text = Text(ans, 'text', [])

        for child in run:
            if is_tag(child, 'w:t'):
                if not child.text:
                    continue
                space = child.get(XML('space'), None)
                if space == 'preserve':
                    text.add_elem(SPAN(child.text, style="whitespace:pre-wrap"))
                    ans.append(text.elem)
                else:
                    text.buf.append(child.text)
            elif is_tag(child, 'w:cr'):
                text.add_elem(BR())
            elif is_tag(child, 'w:br'):
                typ = child.get('type', None)
                if typ in {'column', 'page'}:
                    br = BR(style='page-break-after:always')
                else:
                    clear = child.get('clear', None)
                    if clear in {'all', 'left', 'right'}:
                        br = BR(style='clear:%s'%('both' if clear == 'all' else clear))
                    else:
                        br = BR()
                text.add_elem(br)
        if text.buf:
            setattr(text.elem, text.attr, ''.join(text.buf))
        return ans

if __name__ == '__main__':
    from calibre.utils.logging import default_log
    default_log.filter_level = default_log.DEBUG
    Convert(sys.argv[-1], log=default_log)()
