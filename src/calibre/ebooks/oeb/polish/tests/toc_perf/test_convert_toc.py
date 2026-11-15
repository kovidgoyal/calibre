#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>
'''Correctness and call-count gates for convert TOC construction (line B).'''

from __future__ import annotations

import os
import time
import unittest
from typing import Any
from unittest import mock

from lxml import etree

from calibre.ebooks.oeb.base import TOC
from calibre.ebooks.oeb.polish.tests.base import BaseTest, build_book
from calibre.ebooks.oeb.polish.tests.toc_perf import generators as gen
from calibre.ebooks.oeb.polish.tests.toc_perf.baselines import record_baseline
from calibre.ebooks.oeb.polish.tests.toc_perf.gates import maybe_expected_failure
from calibre.ebooks.oeb.polish.tests.toc_perf.scales import fanout_for, scale_n
from calibre.ebooks.oeb.transforms.structure import DetectStructure
from calibre.utils.logging import DevNull


class _FakeItem:
    def __init__(self, href: str, root: etree._Element) -> None:
        self.href = href
        self.data = root


class _FakeSpine(list):
    pass


class _FakeOEB:
    def __init__(self) -> None:
        self.toc = TOC()
        self.spine = _FakeSpine()
        self.log = DevNull()
        self.guide = {}
        self.manifest = None


class _Opts:
    level1_toc = '//h:h1'
    level2_toc = '//h:h2'
    level3_toc = '//h:h3'
    use_auto_toc = True
    no_chapters_in_toc = False
    toc_filter = None
    duplicate_links_in_toc = False
    max_toc_links = 50
    toc_threshold = 6


def _load_html_oeb(html: str) -> _FakeOEB:
    root = etree.fromstring(html.encode('utf-8') if isinstance(html, str) else html)
    oeb = _FakeOEB()
    oeb.spine.append(_FakeItem('index.xhtml', root))
    return oeb


def _run_leveled(oeb: _FakeOEB) -> DetectStructure:
    ds = DetectStructure()
    ds.oeb = oeb
    ds.log = oeb.log
    ds.opts = _Opts()
    ds.add_leveled_toc_items()
    return ds


def _toc_titles(toc: TOC) -> list[str]:
    return [n.title or '' for n in toc.iterdescendants()]


class TOCConvertCorrectness(BaseTest):
    def test_b_levels_s_node_count_and_depth(self) -> None:
        n = scale_n('S')
        oeb = _load_html_oeb(gen.b_levels_html(n))
        _run_leveled(oeb)
        oeb.toc.rationalize_play_orders()
        fanout = fanout_for(n)
        self.assertEqual(oeb.toc.count(), fanout.total_entries)
        # TOC.depth() counts the root as level 1, so three heading levels → 4
        self.assertEqual(oeb.toc.depth(), 4)
        # First L1 has fanout.l2 children
        self.assertEqual(len(oeb.toc.nodes), fanout.l1)
        self.assertEqual(len(oeb.toc.nodes[0].nodes), fanout.l2)
        self.assertEqual(len(oeb.toc.nodes[0].nodes[0].nodes), fanout.l3)

    def test_playorder_invariants_after_rationalize(self) -> None:
        n = scale_n('S')
        toc = TOC()
        # Build conflicting play orders intentionally
        for i in range(n):
            toc.add(f'T{i}', f'f.xhtml#id{i % (n // 2 + 1)}', play_order=1 if i < 10 else i)
        toc.rationalize_play_orders()
        by_po: dict[int, set[str | None]] = {}
        by_href: dict[str | None, set[int]] = {}
        for node in toc.iterdescendants():
            by_po.setdefault(node.play_order, set()).add(node.href)
            by_href.setdefault(node.href, set()).add(node.play_order)
        for hrefs in by_po.values():
            self.assertEqual(len(hrefs), 1, 'same playOrder ⇒ same href')
        for orders in by_href.values():
            self.assertEqual(len(orders), 1, 'same href ⇒ same playOrder')

    def test_leveled_matches_from_xpaths_shape_tiny(self) -> None:
        # Structural parity: depth and titles vs polish from_xpaths semantics on same HTML
        from calibre.ebooks.oeb.polish.container import get_container
        from calibre.ebooks.oeb.polish.tests.structure import create_epub, cmi
        from calibre.ebooks.oeb.polish.toc import from_xpaths

        html = gen.b_levels_html(scale_n('Tiny'))
        ep = os.path.join(self.tdir, 'fx.epub')
        with open(ep, 'wb') as f:
            f.write(create_epub([cmi('index.xhtml', html)]).getvalue())
        c = get_container(ep, tdir=os.path.join(self.tdir, 'fxc'), tweak_mode=True)
        fx = from_xpaths(c, ['//h:h1', '//h:h2', '//h:h3'])
        oeb = _load_html_oeb(html)
        _run_leveled(oeb)
        self.assertEqual(len(fx), len(oeb.toc.nodes))
        self.assertEqual([x.title for x in fx], [x.title for x in oeb.toc.nodes])

    def test_build_book_md_smoke_tiny(self) -> None:
        md = gen.b_levels_path('Tiny', 'md')
        dest = os.path.join(self.tdir, 'tiny.epub')
        build_book(md, dest, args=gen.LEVEL_TOC_OPTS + ['--language=en', '--authors=Test'])
        self.assertTrue(os.path.exists(dest))
        from calibre.ebooks.oeb.polish.container import get_container
        from calibre.ebooks.oeb.polish.toc import get_toc

        c = get_container(dest, tdir=os.path.join(self.tdir, 'tiny-c'), tweak_mode=True)
        toc = get_toc(c)
        self.assertEqual(len(toc), fanout_for(20).l1)


class TOCConvertCallCounts(BaseTest):
    @maybe_expected_failure('b1')
    def test_next_play_order_no_full_tree_scan_while_building(self) -> None:
        n = scale_n('L')
        oeb = _load_html_oeb(gen.b_levels_html(n))
        if not hasattr(TOC, '_max_play_order_scan'):
            self.fail('B1 not landed: incremental next_play_order + _max_play_order_scan')
        scans = {'n': 0}
        original = TOC._max_play_order_scan

        def counting_scan(self: TOC) -> int:
            scans['n'] += 1
            return original(self)

        with mock.patch.object(TOC, '_max_play_order_scan', counting_scan):
            _run_leveled(oeb)
        self.assertEqual(scans['n'], 0)

    @maybe_expected_failure('b1')
    def test_leveled_iterdescendants_bounded_per_doc(self) -> None:
        n = scale_n('L')
        oeb = _load_html_oeb(gen.b_levels_html(n))
        root = oeb.spine[0].data
        calls = {'n': 0}
        real_iter = root.iterdescendants

        def counting_iter(*a: Any, **kw: Any):
            calls['n'] += 1
            return real_iter(*a, **kw)

        with mock.patch.object(root, 'iterdescendants', counting_iter):
            _run_leveled(oeb)
        # After B1: O(docs) passes — allow small constant C (e.g. ≤ 4)
        self.assertLessEqual(calls['n'], 4)

    @maybe_expected_failure('b1')
    def test_rationalize_no_full_tree_conflict_scans(self) -> None:
        n = scale_n('L')
        toc = TOC()
        for i in range(n):
            toc.add(f'T{i}', f'f.xhtml#id{i}', play_order=i + 1)
        if not getattr(TOC.rationalize_play_orders, '_toc_perf_map_based', False):
            self.fail('B1 not landed: map-based rationalize_play_orders')
        toc.rationalize_play_orders()

    @maybe_expected_failure('b2')
    def test_b_sony_stub_gate(self) -> None:
        self.skipTest(gen.b_sony_stub_note() + ' (implemented in PR-B2)')

    @maybe_expected_failure('b2')
    def test_b_inline_stub_gate(self) -> None:
        self.skipTest(gen.b_inline_stub_note() + ' (implemented in PR-B2)')


class TOCConvertBaselines(BaseTest):
    def test_record_l_leveled_wall(self) -> None:
        n = scale_n('L')
        oeb = _load_html_oeb(gen.b_levels_html(n))
        t0 = time.perf_counter()
        _run_leveled(oeb)
        oeb.toc.rationalize_play_orders()
        elapsed = time.perf_counter() - t0
        path = record_baseline('b_levels_L_detect_structure', elapsed, {'n': n})
        self.assertTrue(os.path.exists(path))


if __name__ == '__main__':
    unittest.main(verbosity=2)
