#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>
'''A3 R9: incremental recheck — fail-closed allowlist + run_checks(only=).'''

from __future__ import annotations

import os
import unittest
from typing import TYPE_CHECKING
from unittest import mock

from calibre.ebooks.oeb.polish.check.coalesce import coalesce_toc_link_errors, expand_coalesced_errors
from calibre.ebooks.oeb.polish.check.links import CaseMismatch, DanglingLink, check_links
from calibre.ebooks.oeb.polish.check.main import (
    LINK_ID_FIX_TYPES,
    can_partial_recheck,
    fix_errors,
    run_checks,
)
from calibre.ebooks.oeb.polish.check.parsing import BareTextInBody, InvalidId, check_ids
from calibre.ebooks.oeb.polish.container import get_container
from calibre.ebooks.oeb.polish.tests.base import BaseTest
from calibre.ebooks.oeb.polish.tests.toc_perf import generators as gen
from calibre.ebooks.oeb.polish.tests.toc_perf.gates import maybe_expected_failure

if TYPE_CHECKING:
    from calibre.ebooks.oeb.polish.check.base import BaseError
    from calibre.ebooks.oeb.polish.container import Container


def _open_a(variant: gen.AVariant, scale: str, tdir: str) -> Container:
    path = gen.a_epub_path(variant, scale)
    return get_container(path, tdir=os.path.join(tdir, f'a3r9-{variant}-{scale}'), tweak_mode=True)


def _sig(errors: list[BaseError]) -> set[tuple]:
    '''Stable identity: type + name + message text (exclude line/col from str()).'''
    out = set()
    for e in errors:
        msg = getattr(e, 'msg', None) or (e.args[0] if getattr(e, 'args', None) else str(e))
        out.add((type(e).__name__, e.name, str(msg)))
    return out


class A3PartialRecheckClassification(BaseTest):
    def test_can_partial_recheck_allowlist(self) -> None:
        c = _open_a('dangling', 'Tiny', self.tdir)
        dangling = [e for e in check_links(c) if isinstance(e, DanglingLink)]
        self.assertTrue(can_partial_recheck(dangling))
        c2 = _open_a('invalid_id', 'Tiny', self.tdir)
        invalid = [e for e in check_ids(c2) if isinstance(e, InvalidId)]
        self.assertTrue(can_partial_recheck(invalid))
        self.assertTrue(can_partial_recheck(dangling + invalid))
        self.assertFalse(can_partial_recheck([]))
        # Markup outside allowlist → fail-closed
        bare = BareTextInBody('chapter.xhtml', [1])
        self.assertFalse(can_partial_recheck([dangling[0], bare]))
        self.assertFalse(can_partial_recheck([bare]))
        for cls in LINK_ID_FIX_TYPES:
            self.assertTrue(issubclass(cls, object))

    def test_coalesced_expand_before_classify(self) -> None:
        c = _open_a('dangling', 'Tiny', self.tdir)
        errors = [e for e in check_links(c) if isinstance(e, DanglingLink)]
        coalesced = coalesce_toc_link_errors(errors)
        self.assertTrue(can_partial_recheck(expand_coalesced_errors(coalesced)))


class A3PartialRecheckEquivalence(BaseTest):
    def test_partial_matches_filtered_full_after_dangling_fix(self) -> None:
        c = _open_a('dangling', 'Tiny', self.tdir)
        errors = [e for e in check_links(c) if isinstance(e, DanglingLink)]
        fix_errors(c, errors)
        partial = run_checks(c, only=frozenset({'links', 'ids'}))
        direct = check_links(c) + check_ids(c)
        self.assertEqual(_sig(partial), _sig(direct))
        # Same (type, name, msg) appear among full-suite errors of those checkers' classes
        full = run_checks(c)
        partial_types = {type(e) for e in partial}
        filtered = [e for e in full if type(e) in partial_types]
        self.assertEqual(_sig(partial), _sig(filtered))

    def test_partial_matches_filtered_full_after_invalid_id_fix(self) -> None:
        c = _open_a('invalid_id', 'Tiny', self.tdir)
        errors = [e for e in check_ids(c) if isinstance(e, InvalidId)]
        fix_errors(c, errors)
        partial = run_checks(c, only=frozenset({'links', 'ids'}))
        direct = check_links(c) + check_ids(c)
        self.assertEqual(_sig(partial), _sig(direct))
        full = run_checks(c)
        partial_types = {type(e) for e in partial}
        filtered = [e for e in full if type(e) in partial_types]
        self.assertEqual(_sig(partial), _sig(filtered))


class A3PartialRecheckCallSkip(BaseTest):
    @maybe_expected_failure('a3')
    def test_partial_skips_css_fonts_markup(self) -> None:
        c = _open_a('dangling', 'Tiny', self.tdir)
        with mock.patch('calibre.ebooks.oeb.polish.check.main.CSSChecker') as css_cls:
            with mock.patch('calibre.ebooks.oeb.polish.check.main.check_fonts') as fonts:
                with mock.patch('calibre.ebooks.oeb.polish.check.main.check_markup') as markup:
                    with mock.patch('calibre.ebooks.oeb.polish.check.main.check_links', wraps=check_links) as links:
                        with mock.patch('calibre.ebooks.oeb.polish.check.main.check_ids', wraps=check_ids) as ids:
                            run_checks(c, only=frozenset({'links', 'ids'}))
        css_cls.assert_not_called()
        fonts.assert_not_called()
        markup.assert_not_called()
        self.assertEqual(links.call_count, 1)
        self.assertEqual(ids.call_count, 1)

    def test_unknown_only_token_falls_back_to_full(self) -> None:
        c = _open_a('clean', 'Tiny', self.tdir)
        with mock.patch('calibre.ebooks.oeb.polish.check.main.check_fonts', wraps=__import__(
            'calibre.ebooks.oeb.polish.check.fonts', fromlist=['check_fonts']
        ).check_fonts) as fonts:
            with mock.patch('calibre.ebooks.oeb.polish.check.main.CSSChecker') as css_cls:
                # Force CSSChecker to no-op but still count construction
                css_cls.return_value = mock.Mock(return_value=())
                run_checks(c, only=frozenset({'links', 'fonts'}))
        fonts.assert_called()

    def test_full_path_unchanged_only_none(self) -> None:
        c = _open_a('clean', 'Tiny', self.tdir)
        with mock.patch('calibre.ebooks.oeb.polish.check.main.check_fonts') as fonts:
            with mock.patch('calibre.ebooks.oeb.polish.check.main.check_markup') as markup:
                with mock.patch('calibre.ebooks.oeb.polish.check.main.check_links', return_value=[]):
                    with mock.patch('calibre.ebooks.oeb.polish.check.main.check_ids', return_value=[]):
                        with mock.patch('calibre.ebooks.oeb.polish.check.main.CSSChecker') as css_cls:
                            css_cls.return_value = mock.Mock(return_value=())
                            run_checks(c, only=None)
        fonts.assert_called()
        markup.assert_called()

    def test_fail_closed_mixed_with_markup_implies_full_suite(self) -> None:
        '''Classification gate: InvalidId + BareTextInBody → not partial.'''
        c = _open_a('invalid_id', 'Tiny', self.tdir)
        invalid = [e for e in check_ids(c) if isinstance(e, InvalidId)][:1]
        bare = BareTextInBody(gen.CHAPTER, [1])
        self.assertFalse(can_partial_recheck(invalid + [bare]))
        # Spy: when caller would use can_partial_recheck, full path runs fonts
        with mock.patch('calibre.ebooks.oeb.polish.check.main.check_fonts') as fonts:
            with mock.patch('calibre.ebooks.oeb.polish.check.main.CSSChecker') as css_cls:
                css_cls.return_value = mock.Mock(return_value=())
                if can_partial_recheck(invalid + [bare]):
                    run_checks(c, only=frozenset({'links', 'ids'}))
                else:
                    run_checks(c)
        fonts.assert_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
