#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>
'''A2 follow-ups: UI coalesce helpers + single-pass link/destination checks.'''

from __future__ import annotations

import os
import unittest

from calibre.ebooks.oeb.polish.check.coalesce import coalesce_toc_link_errors, expand_coalesced_errors
from calibre.ebooks.oeb.polish.check.links import BadDestinationFragment, CaseMismatch, DanglingLink, check_link_destinations, check_links
from calibre.ebooks.oeb.polish.check.main import run_checks
from calibre.ebooks.oeb.polish.container import get_container
from calibre.ebooks.oeb.polish.tests.base import BaseTest
from calibre.ebooks.oeb.polish.tests.toc_perf import generators as gen
from calibre.ebooks.oeb.polish.tests.toc_perf.gates import case_sensitive_fs


def _open_a(variant: gen.AVariant, scale: str, tdir: str):
    path = gen.a_epub_path(variant, scale)
    return get_container(path, tdir=os.path.join(tdir, f'a2-{variant}-{scale}'), tweak_mode=True)


class A2CoalesceTests(BaseTest):
    def test_coalesce_dangling_by_target(self) -> None:
        c = _open_a('dangling', 'Tiny', self.tdir)
        errors = [e for e in check_links(c) if isinstance(e, DanglingLink)]
        self.assertGreater(len(errors), 5)
        coalesced = coalesce_toc_link_errors(errors)
        self.assertEqual(len(coalesced), 1)
        primary = coalesced[0]
        self.assertTrue(primary.has_multiple_locations)
        self.assertEqual(len(primary.all_locations or []), len(errors))
        expanded = expand_coalesced_errors(coalesced)
        self.assertEqual(len(expanded), len(errors))

    def test_coalesce_case_by_source_file(self) -> None:
        if not case_sensitive_fs(self.tdir):
            self.skipTest('case-sensitive FS required')
        c = _open_a('case', 'Tiny', self.tdir)
        errors = [e for e in check_links(c) if isinstance(e, CaseMismatch)]
        coalesced = coalesce_toc_link_errors(errors)
        # nav + ncx → at most 2 rows (one per source file)
        self.assertLessEqual(len(coalesced), 2)
        self.assertEqual(len(expand_coalesced_errors(coalesced)), len(errors))


class A2MergedLinkDestTests(BaseTest):
    def test_run_checks_reports_bad_fragments_via_check_links(self) -> None:
        if not case_sensitive_fs(self.tdir):
            self.skipTest('case-sensitive FS required')
        c = _open_a('mixed', 'Tiny', self.tdir)
        via_links = [e for e in check_links(c) if isinstance(e, BadDestinationFragment)]
        via_dest_only = [e for e in check_link_destinations(c) if isinstance(e, BadDestinationFragment)]
        self.assertGreater(len(via_links), 0)
        # Single-pass check_links should find the same bad fragments as the legacy dest-only pass
        self.assertEqual(
            sorted((e.name, e.bad_href) for e in via_links),
            sorted((e.name, e.bad_href) for e in via_dest_only),
        )
        via_run = [e for e in run_checks(c) if isinstance(e, BadDestinationFragment)]
        self.assertEqual(len(via_run), len(via_links))


if __name__ == '__main__':
    unittest.main(verbosity=2)
