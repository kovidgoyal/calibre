#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os, subprocess

from calibre.ebooks.oeb.polish.tests.base import BaseTest, get_simple_book

from calibre.ebooks.oeb.polish.container import get_container as _gc, clone_container, OCF_NS
from calibre.ebooks.oeb.polish.replace import rename_files
from calibre.utils.filenames import nlinks_file
from calibre.ptempfile import TemporaryFile

def get_container(*args, **kwargs):
    kwargs['tweak_mode'] = True
    return _gc(*args, **kwargs)

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

    def run_external_tools(self, container, gvim=False, epubcheck=True):
        with TemporaryFile(suffix='.epub', dir=self.tdir) as f:
            container.commit(outpath=f)
            if gvim:
                subprocess.Popen(['gvim', '-f', f]).wait()
            if epubcheck:
                subprocess.Popen(['epubcheck', f]).wait()

    def test_file_rename(self):
        ' Test renaming of files '
        book = get_simple_book()
        count = [0]
        def new_container():
            count[0] += 1
            tdir = os.mkdir(os.path.join(self.tdir, str(count[0])))
            return get_container(book, tdir=tdir)

        # Test simple opf rename
        c = new_container()
        orig_name = c.opf_name
        name = 'renamed opf.opf'
        rename_files(c, {c.opf_name: name})
        self.assertEqual(c.opf_name, name)
        for x in ('name_path_map', 'mime_map'):
            self.assertNotIn(orig_name, getattr(c, x))
            self.assertIn(name, getattr(c, x))
        self.assertNotIn(name, c.dirtied)
        root = c.parsed('META-INF/container.xml')
        vals = set(root.xpath(
            r'child::ocf:rootfiles/ocf:rootfile/@full-path',
            namespaces={'ocf':OCF_NS}))
        self.assertSetEqual(vals, {name})
        self.check_links(c)

        # Test a rename that moves the OPF into different directory
        c = new_container()
        orig_name = c.opf_name
        name = 'renamed/again/metadata.opf'
        rename_files(c, {c.opf_name: name})
        self.check_links(c)

        # Test that renaming commits dirtied items
        c = new_container()
        name = next(c.spine_names)[0]
        root = c.parsed(name)
        root.xpath('//*[local-name()="body"]')[0].set('id', 'rename-dirty-test')
        rename_files(c, {name:'other/' + name})
        with c.open('other/' + name) as f:
            raw = f.read()
        self.assertIn(b'id="rename-dirty-test"', raw)
        self.check_links(c)

        # Test renaming of stylesheets
        c = new_container()
        rename_files(c, {'stylesheet.css':'styles/s 1.css', 'page_styles.css':'styles/p 1.css'})
        self.check_links(c)

        # Test renaming of images
        c = new_container()
        rename_files(c, {'cover.png':'images/cover img.png', 'light_wood.png':'images/light wood.png', 'marked.png':'images/marked img.png'})
        self.check_links(c)

        # Test renaming of ToC
        c = new_container()
        rename_files(c, {'toc.ncx': 'toc/toc file.ncx'})
        self.check_links(c)

        # Test renaming of font files
        c = new_container()
        rename_files(c, {'LiberationMono-Regular.ttf': 'fonts/LiberationMono Regular.ttf'})
        self.check_links(c)

        # Test renaming of text files
        c = new_container()
        rename_files(c, {'index_split_000.html':'text/page one fällen.html', 'index_split_001.html':'text/page two fällen.html'})
        self.check_links(c)

        # self.run_external_tools(c, gvim=True)

