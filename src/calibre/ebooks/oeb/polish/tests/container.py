#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os

from calibre.ebooks.oeb.polish.tests.base import BaseTest, get_simple_book

from calibre.ebooks.oeb.polish.container import get_container, clone_container
from calibre.utils.filenames import nlinks_file

class ContainerTests(BaseTest):

    def test_clone(self):
        ' Test cloning of containers '
        for fmt in ('epub', 'azw3'):
            base = os.path.join(self.tdir, fmt + '-')
            book = get_simple_book(fmt)
            tdir = base + 'first'
            os.mkdir(tdir)
            c1 = get_container(book, tdir=tdir)
            tdir = base + 'second'
            os.mkdir(tdir)
            c2 = clone_container(c1, tdir)

            for c in (c1, c2):
                for name, path in c.name_path_map.iteritems():
                    self.assertEqual(2, nlinks_file(path), 'The file %s is not linked' % name)

            for name in c1.name_path_map:
                self.assertIn(name, c2.name_path_map)
                self.assertEqual(c1.open(name).read(), c2.open(name).read(), 'The file %s differs' % name)

            spine_names = tuple(x[0] for x in c1.spine_names)
            text = spine_names[0]
            root = c2.parsed(text)
            root.xpath('//*[local-name()="body"]')[0].set('id', 'changed id for test')
            c2.dirty(text)
            c2.commit_item(text)
            for c in (c1, c2):
                self.assertEqual(1, nlinks_file(c.name_path_map[text]))
            self.assertNotEqual(c1.open(text).read(), c2.open(text).read())

            name = spine_names[1]
            with c1.open(name, mode='r+b') as f:
                f.seek(0, 2)
                f.write(b'    ')
            for c in (c1, c2):
                self.assertEqual(1, nlinks_file(c.name_path_map[name]))
            self.assertNotEqual(c1.open(name).read(), c2.open(name).read())

            x = base + 'out.' + fmt
            for c in (c1, c2):
                c.commit(outpath=x)

    def test_file_removal(self):
        ' Test removal of files from the container '
        book = get_simple_book()
        c = get_container(book, tdir=self.tdir)
        files = ('toc.ncx', 'cover.png', 'titlepage.xhtml')
        self.assertIn('titlepage.xhtml', {x[0] for x in c.spine_names})
        self.assertTrue(c.opf_xpath('//opf:meta[@name="cover"]'))
        for x in files:
            c.remove_item(x)
        self.assertIn(c.opf_name, c.dirtied)
        self.assertNotIn('titlepage.xhtml', {x[0] for x in c.spine_names})
        self.assertFalse(c.opf_xpath('//opf:meta[@name="cover"]'))
        raw = c.serialize_item(c.opf_name).decode('utf-8')
        for x in files:
            self.assertNotIn(x, raw)

