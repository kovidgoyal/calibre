#!/usr/bin/env python
# License: GPLv3

import os
from itertools import count
from typing import TYPE_CHECKING
from unittest.mock import patch

from calibre.ebooks.oeb.polish.container import get_container
from calibre.ebooks.oeb.polish.main import Opts, check_and_fix, option_parser, polish_one
from calibre.ebooks.oeb.polish.tests.base import BaseTest
from calibre.ebooks.oeb.polish.tests.structure import cmi, create_epub
from calibre.utils.resources import get_image_path

if TYPE_CHECKING:
    import unittest
    from collections.abc import Sequence

    from calibre.ebooks.oeb.polish.container import Container
    from calibre.ebooks.oeb.polish.tests.structure import ManifestItem

counter = count()


def html(body: str) -> str:
    return f'<html xmlns="http://www.w3.org/1999/xhtml"><head><title>t</title></head><body>{body}</body></html>'


class PolishActionsTest(BaseTest):
    def create_epub_file(self, manifest: Sequence[ManifestItem], meta_cover: str | None = None, ver: int = 3, spine: Sequence[str] = ()) -> str:
        ep = os.path.join(self.tdir, f'{next(counter)}book.epub')
        with open(ep, 'wb') as f:
            f.write(create_epub(manifest, spine=spine, meta_cover=meta_cover, ver=ver).getvalue())
        return ep

    def open_container(self, path: str) -> Container:
        return get_container(path, tdir=os.path.join(self.tdir, f'container{next(counter)}'), tweak_mode=True)

    def create_epub(self, manifest: Sequence[ManifestItem], meta_cover: str | None = None, ver: int = 3, spine: Sequence[str] = ()) -> Container:
        return self.open_container(self.create_epub_file(manifest, meta_cover, ver, spine))

    def raw(self, c: Container, name: str) -> str:
        c.commit_item(name, keep_parsed=False)
        data = c.raw_data(name)
        assert isinstance(data, str)  # decode=True is the default
        return data

    def test_cleanup_cli_option(self) -> None:
        opts, _ = option_parser().parse_args(['--cleanup', 'x.epub'])
        self.assertTrue(opts.cleanup)

    def test_cleanup(self) -> None:
        with open(get_image_path('blank.png'), 'rb') as f:
            png = f.read()
        path = self.create_epub_file(
            [
                cmi('a.html', html('<p id="1x">one<p>two<div><img src="used.png" alt="u"/></body>') + '<a href="#1x">l</a><a href="B.html">c</a>'),
                cmi('b.html', html('<p>b</p>')),
                cmi('s.css', 'p{color:red;margin:0}'),
                cmi('used.png', png),
                cmi('unused.png', b'corrupted image'),
                cmi('cover.png', png),
            ],
            meta_cover='cover.png',
            ver=2,
        )
        outpath = os.path.join(self.tdir, 'cleaned.epub')
        c = self.open_container(path)
        report: list[str] = []
        # Do not use the rules skipped in the editor by the user running the tests
        with patch('calibre.ebooks.oeb.polish.main.check_book_skipped_rules', return_value=frozenset()):
            changed = polish_one(c, Opts(cleanup=True), report.append)
        c.commit(outpath)
        self.assertTrue(changed)
        c = self.open_container(outpath)
        # HTML was fixed and the .html files renamed to .xhtml by the check book fixes
        self.assertEqual(sorted(n for n in c.mime_map if n.endswith('html')), ['a.xhtml', 'b.xhtml'])
        a = self.raw(c, 'a.xhtml')
        self.assertIn('</p>', a)
        self.assertIn('</div>', a)
        self.assertIn('href="b.xhtml"', a)
        self.assertIn('id="id1x"', a)
        # Unused images were removed, but not the cover
        self.assertIn('used.png', c.mime_map)
        self.assertIn('cover.png', c.mime_map)
        self.assertNotIn('unused.png', c.mime_map)
        # Files were beautified
        self.assertIn('\n', a.partition('<body')[2])
        self.assertIn('\n', self.raw(c, 's.css').strip())
        self.assertNotIn('<manifest><item', self.raw(c, c.opf_name))
        self.assertTrue(any(x.startswith('Fixed') for x in report), report)

    def test_remove_unused_images(self) -> None:
        from calibre.ebooks.oeb.polish.images import remove_unused_images

        c = self.create_epub(
            [
                cmi('a.xhtml', html('<link rel="stylesheet" href="s.css"/><img src="used.png" alt="u"/>')),
                cmi('nav.xhtml', html('<img src="nav.png" alt="n"/>'), 'nav'),
                cmi('s.css', '@import "i.css";'),
                cmi('i.css', 'p { background-image: url(imported.png) }'),
                cmi('used.png'),
                cmi('nav.png'),
                cmi('imported.png'),
                cmi('cover.png', properties='cover-image'),
                cmi('unused.png'),
            ],
            spine=['a.xhtml'],
        )
        self.assertTrue(remove_unused_images(c))
        self.assertEqual(sorted(n for n in c.mime_map if n.endswith('.png')), ['cover.png', 'imported.png', 'nav.png', 'used.png'])
        self.assertFalse(remove_unused_images(c))

    def test_remove_unused_images_svg(self) -> None:
        from calibre.ebooks.oeb.polish.images import remove_unused_images

        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">'
            '<style>rect { fill: url(styled.png) }</style>'
            '<image xlink:href="in_svg.png"/><image href="nested.svg"/><rect/></svg>'
        )
        nested = '<svg xmlns="http://www.w3.org/2000/svg"><image href="in_nested.png"/></svg>'
        c = self.create_epub([
            cmi('a.xhtml', html('<img src="i.svg" alt="i"/>')),
            cmi('i.svg', svg),
            cmi('nested.svg', nested),
            cmi('unused.svg', '<svg xmlns="http://www.w3.org/2000/svg"><image href="only_unused_svg.png"/></svg>'),
            cmi('in_svg.png'),
            cmi('styled.png'),
            cmi('in_nested.png'),
            cmi('only_unused_svg.png'),
        ])
        self.assertTrue(remove_unused_images(c))
        self.assertEqual(sorted(n for n in c.mime_map if n.endswith(('.png', '.svg'))), ['i.svg', 'in_nested.png', 'in_svg.png', 'nested.svg', 'styled.png'])
        self.assertFalse(remove_unused_images(c))
        # Nothing is removed when a referenced SVG cannot be parsed, as it
        # might reference any image
        c = self.create_epub([cmi('a.xhtml', html('<img src="i.svg" alt="i"/>')), cmi('i.svg', b'\0'), cmi('unused.png')])
        report: list[str] = []
        self.assertFalse(remove_unused_images(c, report.append))
        self.assertIn('unused.png', c.mime_map)
        self.assertTrue(any('Failed to parse' in x for x in report), report)

    def test_check_and_fix(self) -> None:
        from calibre.ebooks.oeb.polish.check.main import run_checks

        c = self.create_epub([cmi('a.html', html('<p id="1x">a</p><a href="#1x">l</a>'))], ver=2)
        report: list[str] = []
        self.assertTrue(check_and_fix(c, report.append, frozenset()))
        self.assertEqual([str(e) for e in run_checks(c)], [])
        report = []
        self.assertFalse(check_and_fix(c, report.append, frozenset()))
        self.assertEqual(report, ['No errors found'])

    def test_check_and_fix_multiple_passes(self) -> None:
        from calibre.ebooks.oeb.polish.check.main import run_checks

        # The malformed SVG is a fatal error that prevents the invalid ids from
        # being found until it is fixed
        c = self.create_epub(
            [
                cmi('a.xhtml', html('<p id="1x">a</p><p id="2x">b</p><img src="i.svg" alt="i"/>')),
                cmi('i.svg', '<svg xmlns="http://www.w3.org/2000/svg"><rect></svg>'),
            ],
            ver=2,
        )
        report: list[str] = []
        self.assertTrue(check_and_fix(c, report.append, frozenset()))
        self.assertEqual([str(e) for e in run_checks(c)], [])
        self.assertIn('Found 3 errors', report)
        self.assertIn('Fixed 3 errors', report)

    def test_check_and_fix_reports_unfixable(self) -> None:
        # An EPUB 3 book without a navigation document cannot be fixed automatically
        c = self.create_epub([cmi('a.xhtml', html('<p>a</p>'))])
        report: list[str] = []
        check_and_fix(c, report.append, frozenset())
        self.assertTrue(any('could not be fixed' in x for x in report), report)
        self.assertTrue(any(x.startswith('  [Error] content.opf') for x in report), report)

    def test_check_and_fix_skipped_rules(self) -> None:
        c = self.create_epub([cmi('a.xhtml', html('<p id="1x">a</p>'))], ver=2)
        report: list[str] = []
        self.assertFalse(check_and_fix(c, report.append, frozenset({'InvalidId'})))
        self.assertEqual(report, ['No errors found'])
        self.assertIn('id="1x"', self.raw(c, 'a.xhtml'))


def find_tests() -> unittest.TestSuite:
    import unittest

    return unittest.defaultTestLoader.loadTestsFromTestCase(PolishActionsTest)


if __name__ == '__main__':
    from calibre.utils.run_tests import run_cli

    run_cli(find_tests())
