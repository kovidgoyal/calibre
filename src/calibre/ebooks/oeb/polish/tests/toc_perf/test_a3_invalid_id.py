#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>
'''A3 R5: batch InvalidId — correctness + replace_ids / CSS rename call-count gates.'''

from __future__ import annotations

import os
import unittest
from typing import TYPE_CHECKING
from unittest import mock

from calibre.ebooks.oeb.base import OEB_DOCS, XHTML
from calibre.ebooks.oeb.polish.check.links import CaseMismatch, DanglingLink, check_links
from calibre.ebooks.oeb.polish.check.main import fix_errors, run_checks
from calibre.ebooks.oeb.polish.check.parsing import InvalidId, check_ids, valid_id
from calibre.ebooks.oeb.polish.container import get_container
from calibre.ebooks.oeb.polish.css import rename_ids_in_css
from calibre.ebooks.oeb.polish.replace import replace_ids
from calibre.ebooks.oeb.polish.tests.base import BaseTest
from calibre.ebooks.oeb.polish.tests.structure import cmi, create_epub
from calibre.ebooks.oeb.polish.tests.toc_perf import generators as gen
from calibre.ebooks.oeb.polish.tests.toc_perf.gates import case_sensitive_fs, gates_enabled, maybe_expected_failure
from calibre.ebooks.oeb.polish.utils import guess_type

if TYPE_CHECKING:
    from collections.abc import Sequence

    from calibre.ebooks.oeb.polish.container import Container
    from calibre.ebooks.oeb.polish.tests.structure import ManifestItem


def _open_a(variant: gen.AVariant, scale: str, tdir: str, **kw) -> Container:
    path = gen.a_epub_path(variant, scale, **kw)
    return get_container(path, tdir=os.path.join(tdir, f'a3-{variant}-{scale}'), tweak_mode=True)


def _nav_hrefs(container: Container) -> list[str]:
    out: list[str] = []
    for name in container.manifest_items_with_property('nav'):
        root = container.parsed(name)
        for a in root.xpath('//*[local-name()="a" and @href]'):
            out.append(a.get('href') or '')
    return out


def _ncx_srcs(container: Container) -> list[str]:
    ncx_mt = guess_type('a.ncx')
    out: list[str] = []
    for name, mt in container.mime_map.items():
        if mt != ncx_mt:
            continue
        root = container.parsed(name)
        for el in root.xpath('//*[@src]'):
            out.append(el.get('src') or '')
    return out


class A3InvalidIdCorrectness(BaseTest):
    def _create(self, manifest: Sequence[ManifestItem], spine: Sequence[str] = (), ver: int = 3) -> Container:
        ep = os.path.join(self.tdir, 'book.epub')
        with open(ep, 'wb') as f:
            f.write(create_epub(manifest, spine, ver=ver).getvalue())
        return get_container(ep, tdir=os.path.join(self.tdir, 'container'), tweak_mode=True)

    def test_a_invalid_id_tiny_clears_and_updates_toc(self) -> None:
        c = _open_a('invalid_id', 'Tiny', self.tdir)
        errors = [e for e in check_ids(c) if isinstance(e, InvalidId)]
        self.assertGreater(len(errors), 5)
        self.assertTrue(fix_errors(c, errors))
        self.assertFalse([e for e in check_ids(c) if isinstance(e, InvalidId)])
        for href in _nav_hrefs(c):
            frag = href.partition('#')[2]
            if frag:
                self.assertIsNotNone(valid_id.match(frag))
        for src in _ncx_srcs(c):
            frag = src.partition('#')[2]
            if frag:
                self.assertIsNotNone(valid_id.match(frag))

    def test_a_invalid_id_dedupe_shared_across_html(self) -> None:
        c = _open_a('invalid_id', 'Tiny', self.tdir)
        errors = [e for e in check_ids(c) if isinstance(e, InvalidId)]
        first_invalid = gen.invalid_id_for_frag('h1-1')
        shared = [e for e in errors if e.invalid_id == first_invalid]
        self.assertGreaterEqual(len(shared), 2)
        fix_errors(c, errors)
        root = c.parsed(gen.CHAPTER)
        # First L1 heading (h1-1) shares its renamed id with chapter2
        h1 = root.xpath('//*[local-name()="h1"]')[0]
        nid = h1.get('id')
        self.assertNotEqual(nid, first_invalid)
        self.assertIsNotNone(valid_id.match(nid))
        root2 = c.parsed(gen.CHAPTER2)
        self.assertEqual(root2.xpath('//*[@id]/@id'), [nid])
        # CSS selectors for the shared invalid id retargeted (first rule is h1-1)
        sheet = c.parsed(gen.STYLE)
        self.assertEqual(sheet.cssRules[0].selectorText, f'#{nid}')

    def test_non_html_invalid_id_local_no_css(self) -> None:
        html = (
            '<html xmlns="http://www.w3.org/1999/xhtml"><head>'
            '<link rel="stylesheet" href="style.css"/></head>'
            '<body><p id="ok">x</p></body></html>'
        )
        ncx = (
            '<?xml version="1.0"?>'
            '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
            '<head><meta name="dtb:uid" content="t"/></head>'
            '<docTitle><text>t</text></docTitle>'
            '<navMap><navPoint id="_bad"><navLabel><text>a</text></navLabel>'
            '<content src="a.html"/></navPoint></navMap></ncx>'
        )
        c = self._create(
            [
                cmi('a.html', html),
                cmi('toc.ncx', ncx),
                cmi('style.css', '#_unrelated { color: blue }\n#ok { color: red }'),
            ],
            spine=['a.html'],
            ver=2,
        )
        errors = [e for e in check_ids(c) if isinstance(e, InvalidId)]
        self.assertTrue(errors)
        self.assertTrue(all(c.mime_map.get(e.name) not in OEB_DOCS for e in errors))
        with mock.patch('calibre.ebooks.oeb.polish.css.rename_ids_in_css', wraps=rename_ids_in_css) as css_p:
            fix_errors(c, errors)
        self.assertEqual(css_p.call_count, 0)
        self.assertEqual(c.parsed('style.css').cssRules[0].selectorText, '#_unrelated')
        self.assertFalse([e for e in check_ids(c) if isinstance(e, InvalidId)])

    def test_mixed_case_dangling_invalid_id(self) -> None:
        if not case_sensitive_fs(self.tdir):
            self.skipTest('case-sensitive FS required for mixed half')
        c = _open_a('mixed', 'Tiny', self.tdir)
        root = c.parsed(gen.CHAPTER)
        body = root.xpath('//*[local-name()="body"]')[0]
        p = body.makeelement(XHTML('p'))
        p.set('id', '_mixed_x')
        p.text = 'invalid'
        body.append(p)
        c.dirty(gen.CHAPTER)
        before = run_checks(c)
        fixables = [e for e in before if e.INDIVIDUAL_FIX]
        self.assertTrue(any(isinstance(e, CaseMismatch) for e in fixables))
        self.assertTrue(any(isinstance(e, DanglingLink) for e in fixables))
        self.assertTrue(any(isinstance(e, InvalidId) for e in fixables))
        fix_errors(c, fixables)
        self.assertFalse([e for e in check_ids(c) if isinstance(e, InvalidId)])
        link_errs = check_links(c)
        self.assertFalse(any(isinstance(e, CaseMismatch) for e in link_errs))
        hrefs = [a.get('href') for a in c.parsed(gen.CHAPTER).xpath('//*[local-name()="a" and @href]')]
        self.assertTrue(any(h and 'h1-1' in h for h in hrefs))


class A3InvalidIdCallCounts(BaseTest):
    '''Hard call-count gates: one replace_ids + one rename_ids_in_css per fix_errors.'''

    def _create(self, manifest: Sequence[ManifestItem], spine: Sequence[str] = (), ver: int = 3) -> Container:
        ep = os.path.join(self.tdir, 'book.epub')
        with open(ep, 'wb') as f:
            f.write(create_epub(manifest, spine, ver=ver).getvalue())
        return get_container(ep, tdir=os.path.join(self.tdir, 'container'), tweak_mode=True)

    @maybe_expected_failure('a3')
    def test_a_invalid_id_l_replace_ids_once(self) -> None:
        c = _open_a('invalid_id', 'L', self.tdir)
        errors = [e for e in check_ids(c) if isinstance(e, InvalidId)]
        self.assertGreaterEqual(len(errors), 50)
        with mock.patch('calibre.ebooks.oeb.polish.replace.replace_ids', wraps=replace_ids) as p_rep:
            with mock.patch('calibre.ebooks.oeb.polish.css.rename_ids_in_css', wraps=rename_ids_in_css) as p_css:
                fix_errors(c, errors)
        if gates_enabled('a3'):
            self.assertEqual(p_rep.call_count, 1, f'replace_ids calls={p_rep.call_count}')
            self.assertEqual(p_css.call_count, 1, f'rename_ids_in_css calls={p_css.call_count}')
        self.assertFalse([e for e in check_ids(c) if isinstance(e, InvalidId)])

    @maybe_expected_failure('a3')
    def test_non_html_only_zero_css_renames(self) -> None:
        ncx = (
            '<?xml version="1.0"?>'
            '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
            '<head><meta name="dtb:uid" content="t"/></head>'
            '<docTitle><text>t</text></docTitle><navMap>'
            + ''.join(
                f'<navPoint id="_n{i}"><navLabel><text>a{i}</text></navLabel>'
                f'<content src="a.html"/></navPoint>'
                for i in range(5)
            )
            + '</navMap></ncx>'
        )
        c = self._create(
            [
                cmi('a.html', '<html xmlns="http://www.w3.org/1999/xhtml"><body><p id="ok">x</p></body></html>'),
                cmi('toc.ncx', ncx),
                cmi('style.css', '#_n0 { color: red }'),
            ],
            spine=['a.html'],
            ver=2,
        )
        errors = [e for e in check_ids(c) if isinstance(e, InvalidId)]
        self.assertGreaterEqual(len(errors), 5)
        with mock.patch('calibre.ebooks.oeb.polish.replace.replace_ids', wraps=replace_ids) as p_rep:
            with mock.patch('calibre.ebooks.oeb.polish.css.rename_ids_in_css', wraps=rename_ids_in_css) as p_css:
                fix_errors(c, errors)
        if gates_enabled('a3'):
            self.assertEqual(p_rep.call_count, 1)
            self.assertEqual(p_css.call_count, 0)
        self.assertEqual(c.parsed('style.css').cssRules[0].selectorText, '#_n0')
        self.assertFalse([e for e in check_ids(c) if isinstance(e, InvalidId)])


if __name__ == '__main__':
    unittest.main(verbosity=2)
