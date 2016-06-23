#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

import os
from calibre.ebooks.oeb.polish.tests.base import BaseTest
from calibre.ebooks.oeb.polish.container import get_container
from calibre.ebooks.oeb.polish.create import create_book
from calibre.ebooks.oeb.polish.toc import get_toc
from calibre.ebooks.metadata.book.base import Metadata

class Structure(BaseTest):

    def test_toc_detection(self):
        ep = os.path.join(self.tdir, 'book.epub')
        create_book(Metadata('Test ToC'), ep)
        c = get_container(ep, tdir=os.path.join(self.tdir, 'container'), tweak_mode=True)
        self.assertEqual(2, c.opf_version_parsed.major)
        self.assertTrue(len(get_toc(c)))
        c.opf.set('version', '3.0')
        self.assertEqual(3, c.opf_version_parsed.major)
        self.assertTrue(len(get_toc(c)))  # detect NCX toc even in epub 3 files
        c.add_file('nav.html', b'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">'
                   '<body><nav epub:type="toc"><ol><li><a href="start.xhtml">EPUB 3 nav</a></li></ol></nav></body></html>',
                   process_manifest_item=lambda item:item.set('properties', 'nav'))
        toc = get_toc(c)
        self.assertTrue(len(toc))
        self.assertEqual(toc.as_dict['children'][0]['title'], 'EPUB 3 nav')
