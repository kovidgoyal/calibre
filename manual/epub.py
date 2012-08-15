#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, time, glob

from lxml import etree

from sphinx.builders.epub import EpubBuilder

class EPUBHelpBuilder(EpubBuilder):
    name = 'myepub'

    def add_cover(self, outdir, cover_fname):
        href = '_static/'+cover_fname
        opf = os.path.join(self.outdir, 'content.opf')

        cover = '''\
        <html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
            <head>
                <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
                <meta name="calibre:cover" content="true" />
                <title>Cover</title>
                <style type="text/css" title="override_css">
                    @page {padding: 0pt; margin:0pt}
                    body { text-align: center; padding:0pt; margin: 0pt; }
                </style>
            </head>
            <body>
                <svg version="1.1" xmlns="http://www.w3.org/2000/svg"
                    xmlns:xlink="http://www.w3.org/1999/xlink"
                    width="100%%" height="100%%" viewBox="0 0 600 800"
                    preserveAspectRatio="none">
                    <image width="600" height="800" xlink:href="%s"/>
                </svg>
            </body>
        </html>
        '''%href
        self.files.append('epub_titlepage.html')
        open(os.path.join(outdir, self.files[-1]), 'wb').write(cover)


        raw = open(opf, 'rb').read()
        raw = raw.replace('</metadata>',
                ('<meta name="cover" content="%s"/>\n'
                 '<dc:date>%s</dc:date>\n</metadata>') %
                (href.replace('/', '_'), time.strftime('%Y-%m-%d')))
        raw = raw.replace('</manifest>',
                ('<item id="{0}" href="{0}" media-type="application/xhtml+xml"/>\n</manifest>').\
                        format('epub_titlepage.html'))
        open(opf, 'wb').write(raw)

    def build_epub(self, outdir, *args, **kwargs):
        if self.config.kovid_epub_cover:
            self.add_cover(outdir, self.config.kovid_epub_cover)
        self.fix_duplication_bugs(outdir)
        EpubBuilder.build_epub(self, outdir, *args, **kwargs)

    def fix_duplication_bugs(self, outdir):
        opf = glob.glob(outdir+os.sep+'*.opf')[0]
        root = etree.fromstring(open(opf, 'rb').read())
        seen = set()
        for x in root.xpath(
                '//*[local-name()="spine"]/*[local-name()="itemref"]'):
            idref = x.get('idref')
            if idref in seen:
                x.getparent().remove(x)
            else:
                seen.add(idref)

        with open(opf, 'wb') as f:
            f.write(etree.tostring(root, encoding='utf-8', xml_declaration=True))


        ncx = glob.glob(outdir+os.sep+'*.ncx')[0]
        root = etree.fromstring(open(ncx, 'rb').read())
        seen = set()
        for x in root.xpath(
                '//*[local-name()="navMap"]/*[local-name()="navPoint"]'):
            text = x.xpath('descendant::*[local-name()="text"]')[0]
            text = text.text
            if text in seen:
                x.getparent().remove(x)
            else:
                seen.add(text)

        with open(ncx, 'wb') as f:
            f.write(etree.tostring(root, encoding='utf-8', xml_declaration=True))


