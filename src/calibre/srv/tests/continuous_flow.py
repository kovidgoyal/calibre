#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Pavezi

import hashlib
import json
import os
import unittest
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from calibre.ebooks.oeb.polish.container import get_container
from calibre.ebooks.oeb.polish.tests.structure import cmi, create_epub
from calibre.ebooks.oeb.polish.toc import get_toc
from calibre.srv.render_book import merge_flow_spine, render_for_viewer

ENV = 'CALIBRE_EXPERIMENTAL_CONTINUOUS_FLOW'


class ContinuousFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'book.epub'
        first = '''<html xmlns="http://www.w3.org/1999/xhtml"><head><title>First</title></head>
<body><h1 id="chapter">First chapter</h1><p>End of first chapter.</p>
<a href="parts/second.xhtml#chapter">Next</a></body></html>'''
        second = '''<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Second</title></head>
<body><h1 id="chapter">Second chapter</h1><p>Start of second chapter.</p>
<a href="../first.xhtml#chapter">Previous</a><img src="../image.svg"/></body></html>'''
        nav = '''<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<body><nav epub:type="toc"><ol><li><a href="first.xhtml#chapter">First</a></li>
<li><a href="parts/second.xhtml#chapter">Second</a></li></ol></nav></body></html>'''
        self.path.write_bytes(
            create_epub(
                [
                    cmi('first.xhtml', first),
                    cmi('parts/second.xhtml', second),
                    cmi('nav.xhtml', nav, 'nav'),
                    cmi('image.svg', '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>'),
                ],
                spine=['first.xhtml', 'parts/second.xhtml'],
            ).getvalue()
        )

    def test_merge_preserves_text_links_and_toc(self):
        c = get_container(str(self.path))
        before = [''.join(c.parsed(n).xpath('//*[local-name()="body"]')[0].itertext()) for n, _ in c.spine_names]
        self.assertTrue(merge_flow_spine(c, None))
        self.assertEqual(list(c.spine_names), [('first.xhtml', True)])
        root = c.parsed('first.xhtml')
        combined = ''.join(root.xpath('//*[local-name()="body"]')[0].itertext())
        for text in before:
            self.assertIn(text.strip(), combined)
        ids = root.xpath('//@id')
        self.assertEqual(len(ids), len(set(ids)))
        for node in get_toc(c).iterdescendants():
            if node.dest:
                self.assertEqual(node.dest, 'first.xhtml')
                self.assertIn(node.frag, ids)
        for href in root.xpath('//*[local-name()="a"]/@href'):
            name, _, frag = href.partition('#')
            self.assertEqual(c.href_to_name(name, 'first.xhtml') if name else 'first.xhtml', 'first.xhtml')
            self.assertIn(frag, ids)
        self.assertEqual(root.xpath('//*[local-name()="img"]/@src'), ['image.svg'])

    def test_single_content_file_is_not_merged(self):
        c = get_container(str(self.path))
        self.assertFalse(merge_flow_spine(c, 'first.xhtml'))
        self.assertEqual(len(list(c.spine_names)), 2)

    def test_unsupported_layouts_are_not_merged(self):
        for reason in ('fixed', 'fixed-item', 'overlay', 'nonlinear'):
            with self.subTest(reason=reason):
                c = get_container(str(self.path))
                if reason == 'fixed':
                    metadata = c.opf_xpath('//opf:metadata')[0]
                    el = metadata.makeelement('{http://www.idpf.org/2007/opf}meta', property='rendition:layout')
                    el.text = 'pre-paginated'
                    metadata.append(el)
                elif reason == 'fixed-item':
                    c.opf_xpath('//opf:spine/opf:itemref')[1].set('properties', 'rendition:layout-pre-paginated')
                elif reason == 'overlay':
                    c.add_file('overlay.smil', b'<smil/>', media_type='application/smil+xml')
                else:
                    c.opf_xpath('//opf:spine/opf:itemref')[1].set('linear', 'no')
                self.assertFalse(merge_flow_spine(c, None))
                self.assertEqual(len(list(c.spine_names)), 2)

    def test_render_is_opt_in_and_leaves_source_unchanged(self):
        before = self.path.read_bytes()
        for enabled in ('0', '1'):
            with self.subTest(enabled=enabled), patch.dict(os.environ, {ENV: enabled}):
                out = Path(self.tmp.name) / ('render-' + enabled)
                out.mkdir()
                render_for_viewer(str(self.path), str(out), 'test')
                manifest = json.loads((out / 'calibre-book-manifest.json').read_bytes())
                self.assertEqual(manifest['continuous_flow'], enabled == '1')
                self.assertEqual(len(manifest['spine']), 1 if enabled == '1' else 2)
                self.assertEqual(self.path.read_bytes(), before)

    def test_render_modes_have_separate_cache_keys(self):
        from calibre.gui2.viewer.convert_book import book_hash
        from calibre.srv.render_book import RENDER_VERSION

        path = str(self.path)
        with patch.dict(os.environ, {ENV: '0'}):
            normal = book_hash(path, 123, 456)
        original = json.dumps((os.path.normcase(os.path.abspath(path)), 123, 456, RENDER_VERSION, 1)).encode()
        self.assertEqual(normal, hashlib.sha1(original).hexdigest())
        with patch.dict(os.environ, {ENV: '1'}):
            self.assertNotEqual(normal, book_hash(path, 123, 456))

    def test_merged_annotations_do_not_write_to_original_or_library(self):
        from calibre.gui2.viewer.annotations import AnnotationsSaveWorker

        worker = AnnotationsSaveWorker()
        data = {
            'annotations_map': defaultdict(list),
            'pathtoebook': str(self.path),
            'annotations_path_key': 'test.continuous.json',
            'book_library_details': {'library': 'original'},
            'continuous_flow': True,
        }
        worker.save_annotations(data, in_book_file=True)
        payload = worker.queue.get_nowait()
        self.assertFalse(payload['in_book_file'])
        self.assertIsNone(payload['book_library_details'])
        data['continuous_flow'] = False
        worker.save_annotations(data, in_book_file=True)
        payload = worker.queue.get_nowait()
        self.assertTrue(payload['in_book_file'])
        self.assertEqual(payload['book_library_details'], {'library': 'original'})
