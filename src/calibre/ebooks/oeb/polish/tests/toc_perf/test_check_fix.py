#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>
'''Correctness and call-count gates for TOC check / auto-fix (line A).'''

from __future__ import annotations

import os
import time
import unittest
from typing import TYPE_CHECKING
from unittest import mock

from calibre.ebooks.oeb.polish.check.links import BadDestinationFragment, CaseMismatch, DanglingLink, check_links
from calibre.ebooks.oeb.polish.check.main import fix_errors, run_checks
from calibre.ebooks.oeb.polish.container import get_container
from calibre.ebooks.oeb.polish.replace import remove_links_to
from calibre.ebooks.oeb.polish.tests.base import BaseTest
from calibre.ebooks.oeb.polish.tests.toc_perf import generators as gen
from calibre.ebooks.oeb.polish.tests.toc_perf.baselines import record_baseline
from calibre.ebooks.oeb.polish.tests.toc_perf.gates import case_sensitive_fs, gates_enabled, maybe_expected_failure
from calibre.ebooks.oeb.polish.utils import guess_type

if TYPE_CHECKING:
    from calibre.ebooks.oeb.polish.container import Container


def _open_a(variant: gen.AVariant, scale: str, tdir: str, **kw) -> Container:
    path = gen.a_epub_path(variant, scale, **kw)
    return get_container(path, tdir=os.path.join(tdir, f'{variant}-{scale}'), tweak_mode=True)


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


def _nav_hrefs(container: Container) -> list[str]:
    out: list[str] = []
    for name in container.manifest_items_with_property('nav'):
        root = container.parsed(name)
        for a in root.xpath('//*[local-name()="a" and @href]'):
            out.append(a.get('href') or '')
    return out


class TOCCheckFixCorrectness(BaseTest):
    def test_a_dangling_tiny_clears_nav_and_ncx_src(self) -> None:
        c = _open_a('dangling', 'Tiny', self.tdir)
        errors = [e for e in check_links(c) if isinstance(e, DanglingLink)]
        self.assertGreater(len(errors), 0)
        fix_errors(c, errors)
        for href in _nav_hrefs(c):
            self.assertFalse(href, f'nav href should be cleared, got {href!r}')
        for src in _ncx_srcs(c):
            self.assertFalse(src, f'NCX src should be cleared, got {src!r}')
        # navPoints retained
        ncx_name = next(n for n, mt in c.mime_map.items() if mt == guess_type('a.ncx'))
        root = c.parsed(ncx_name)
        self.assertGreater(len(root.xpath('//*[local-name()="navPoint"]')), 0)

    def test_a_case_preserves_fragment(self) -> None:
        if not case_sensitive_fs(self.tdir):
            self.skipTest('A-case requires a case-sensitive filesystem')
        c = _open_a('case', 'Tiny', self.tdir)
        errors = [e for e in check_links(c) if isinstance(e, CaseMismatch)]
        self.assertGreater(len(errors), 0)
        fix_errors(c, errors)
        for href in _nav_hrefs(c):
            self.assertIn('#', href)
            self.assertNotIn(gen.CHAPTER_CASE_WRONG, href)
        for src in _ncx_srcs(c):
            self.assertIn('#', src)
            self.assertNotIn(gen.CHAPTER_CASE_WRONG, src)

    def test_case_not_reported_as_dangling(self) -> None:
        if not case_sensitive_fs(self.tdir):
            self.skipTest('A-case requires a case-sensitive filesystem')
        c = _open_a('case', 'Tiny', self.tdir)
        errors = check_links(c)
        self.assertTrue(any(isinstance(e, CaseMismatch) for e in errors))
        self.assertFalse(any(isinstance(e, DanglingLink) for e in errors))

    def test_a_mixed_keeps_body_link_and_bad_fragments(self) -> None:
        if not case_sensitive_fs(self.tdir):
            self.skipTest('A-mixed case half requires a case-sensitive filesystem')
        c = _open_a('mixed', 'Tiny', self.tdir)
        before = run_checks(c)
        frags = [e for e in before if isinstance(e, BadDestinationFragment)]
        self.assertGreater(len(frags), 0)
        fixables = [e for e in before if e.INDIVIDUAL_FIX]
        fix_errors(c, fixables)
        after = run_checks(c)
        self.assertTrue(any(isinstance(e, BadDestinationFragment) for e in after))
        # Body legitimate link still present
        root = c.parsed(gen.CHAPTER)
        hrefs = [a.get('href') for a in root.xpath('//*[local-name()="a" and @href]')]
        self.assertIn('#h1-1', hrefs)

    def test_a_dual_fix_clears_both(self) -> None:
        c = _open_a('dual', 'Tiny', self.tdir)
        errors = [e for e in check_links(c) if isinstance(e, (DanglingLink, CaseMismatch))]
        fix_errors(c, errors)
        self.assertTrue(all(not h for h in _nav_hrefs(c)))
        self.assertTrue(all(not s for s in _ncx_srcs(c)))

    def test_a_clean_no_dangling_or_case(self) -> None:
        c = _open_a('clean', 'Tiny', self.tdir)
        errors = check_links(c)
        self.assertFalse(any(isinstance(e, (DanglingLink, CaseMismatch)) for e in errors))

    def test_single_dangling_fix_still_removes_all_refs(self) -> None:
        c = _open_a('dangling', 'Tiny', self.tdir)
        errors = [e for e in check_links(c) if isinstance(e, DanglingLink)]
        self.assertGreater(len(errors), 0)
        # Individual fix on one error clears all refs to that target
        self.assertIsNot(errors[0](c), False)
        self.assertTrue(all(not h for h in _nav_hrefs(c)))
        self.assertTrue(all(not s for s in _ncx_srcs(c)))


class TOCCheckFixCallCounts(BaseTest):
    '''Hard call-count gates for A1. Soft/xfail until gates_enabled("a1").'''

    @maybe_expected_failure('a1')
    def test_a_dangling_l_remove_links_to_once(self) -> None:
        c = _open_a('dangling', 'L', self.tdir)
        errors = [e for e in check_links(c) if isinstance(e, DanglingLink)]
        self.assertGreater(len(errors), 100)
        with mock.patch('calibre.ebooks.oeb.polish.check.main.remove_links_to', wraps=remove_links_to) as p:
            # Also patch the symbol used by DanglingLink.__call__
            with mock.patch('calibre.ebooks.oeb.polish.check.links.remove_links_to', wraps=remove_links_to) as p2:
                fix_errors(c, errors)
        # Prefer batch path in main; individual path still uses links.remove_links_to
        total = p.call_count + p2.call_count
        # After A1: exactly one batch call via main (and DanglingLink.__call__ skipped)
        if gates_enabled('a1'):
            self.assertEqual(p.call_count, 1)
            self.assertEqual(p2.call_count, 0)
        else:
            self.assertEqual(total, 1)

    @maybe_expected_failure('a1')
    def test_a_dual_l_remove_links_to_once(self) -> None:
        c = _open_a('dual', 'L', self.tdir)
        errors = [e for e in check_links(c) if isinstance(e, DanglingLink)]
        with mock.patch('calibre.ebooks.oeb.polish.check.main.remove_links_to', wraps=remove_links_to) as p:
            with mock.patch('calibre.ebooks.oeb.polish.check.links.remove_links_to', wraps=remove_links_to) as p2:
                fix_errors(c, errors)
        if gates_enabled('a1'):
            self.assertEqual(p.call_count, 1)
            self.assertEqual(p2.call_count, 0)
        self.assertTrue(all(not h for h in _nav_hrefs(c)))
        self.assertTrue(all(not s for s in _ncx_srcs(c)))

    @maybe_expected_failure('a1')
    def test_a_case_l_one_replace_links_per_source(self) -> None:
        if not case_sensitive_fs(self.tdir):
            self.skipTest('A-case requires a case-sensitive filesystem')
        c = _open_a('case', 'L', self.tdir)
        errors = [e for e in check_links(c) if isinstance(e, CaseMismatch)]
        self.assertGreater(len(errors), 100)
        sources = {e.name for e in errors}
        with mock.patch.object(type(c), 'replace_links', wraps=c.replace_links) as p:
            fix_errors(c, errors)
        # One replace_links per source file that had CaseMismatch
        by_name: dict[str, int] = {}
        for call in p.call_args_list:
            name = call.args[0] if call.args else call.kwargs.get('name')
            by_name[name] = by_name.get(name, 0) + 1
        for name in sources:
            self.assertEqual(by_name.get(name, 0), 1, f'replace_links count for {name}')

    @maybe_expected_failure('a1')
    def test_a_clean_l_mime_map_hit_skips_exists(self) -> None:
        c = _open_a('clean', 'L', self.tdir)
        in_map_exists = 0
        real_exists = c.exists

        def counting_exists(name: str) -> bool:
            nonlocal in_map_exists
            if name in c.mime_map:
                in_map_exists += 1
            return real_exists(name)

        with mock.patch.object(type(c), 'exists', side_effect=counting_exists):
            check_links(c)
        self.assertEqual(in_map_exists, 0)


class TOCCheckFixBaselines(BaseTest):
    def test_record_l_dangling_fix_wall(self) -> None:
        '''Record L dangling fix wall time; never asserts a ratio.'''
        c = _open_a('dangling', 'L', self.tdir)
        errors = [e for e in check_links(c) if isinstance(e, DanglingLink)]
        t0 = time.perf_counter()
        fix_errors(c, errors)
        elapsed = time.perf_counter() - t0
        path = record_baseline('a_dangling_L_fix_errors', elapsed, {'n': 2000, 'errors': len(errors)})
        self.assertTrue(os.path.exists(path))


if __name__ == '__main__':
    unittest.main(verbosity=2)
