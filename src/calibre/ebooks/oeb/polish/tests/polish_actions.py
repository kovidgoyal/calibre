#!/usr/bin/env python
# License: GPLv3

import os
from itertools import count
from typing import TYPE_CHECKING

from calibre.ebooks.oeb.polish.container import get_container
from calibre.ebooks.oeb.polish.main import Opts, option_parser, polish_one
from calibre.ebooks.oeb.polish.tests.base import BaseTest
from calibre.ebooks.oeb.polish.tests.structure import cmi, create_epub

if TYPE_CHECKING:
    import unittest
    from collections.abc import Sequence

    from calibre.ebooks.oeb.polish.container import Container
    from calibre.ebooks.oeb.polish.tests.structure import ManifestItem

counter = count()


def html(body: str) -> str:
    return f'<html xmlns="http://www.w3.org/1999/xhtml"><head><title>t</title></head><body>{body}</body></html>'


class PolishActions(BaseTest):
    def create_epub(self, manifest: Sequence[ManifestItem], **kw: object) -> Container:
        n = next(counter)
        ep = os.path.join(self.tdir, f'{n}book.epub')
        with open(ep, 'wb') as f:
            f.write(create_epub(manifest, **kw).getvalue())  # type: ignore[arg-type]
        return get_container(ep, tdir=os.path.join(self.tdir, f'container{n}'), tweak_mode=True)

    def polish(self, c: Container, **actions: bool) -> tuple[bool, list[str]]:
        report: list[str] = []
        changed = polish_one(c, Opts(**actions), report.append)  # type: ignore[arg-type]
        return changed, report

    def raw(self, c: Container, name: str) -> str:
        c.commit_item(name, keep_parsed=False)
        return c.raw_data(name)  # type: ignore[return-value]

    def assert_cli_option(self, option: str, dest: str) -> None:
        opts, _ = option_parser().parse_args([option, 'x.epub'])
        self.assertTrue(getattr(opts, dest))

    def test_check_and_fix(self) -> None:
        from calibre.ebooks.oeb.polish.check.main import run_checks
        from calibre.ebooks.oeb.polish.main import check_and_fix

        self.assert_cli_option('--check-and-fix', 'check_and_fix')
        c = self.create_epub([cmi('a.html', html('<p id="1x">a</p><a href="#1x">l</a><a href="B.html">c</a>')), cmi('b.html', html('<p>b</p>'))], ver=2)
        self.assertTrue(run_checks(c))
        report: list[str] = []
        self.assertTrue(check_and_fix(c, report.append, frozenset()))
        self.assertEqual([str(e) for e in run_checks(c)], [])
        self.assertIn('href="b.xhtml"', self.raw(c, 'a.xhtml'))
        self.assertIn('id="id1x"', self.raw(c, 'a.xhtml'))
        self.assertTrue(any(x.startswith('Fixed') for x in report), report)
        # Nothing left to fix
        report = []
        self.assertFalse(check_and_fix(c, report.append, frozenset()))
        self.assertEqual(report, ['No errors found'])

    def test_check_and_fix_reports_unfixable(self) -> None:
        from calibre.ebooks.oeb.polish.main import check_and_fix

        # An EPUB 3 book without a navigation document cannot be fixed automatically
        c = self.create_epub([cmi('a.xhtml', html('<p>a</p>'))])
        report: list[str] = []
        check_and_fix(c, report.append, frozenset())
        self.assertTrue(any('could not be fixed' in x for x in report), report)
        self.assertTrue(any(x.startswith('  [Error] content.opf') for x in report), report)

    def test_check_and_fix_skipped_rules(self) -> None:
        from calibre.ebooks.oeb.polish.main import check_and_fix

        c = self.create_epub([cmi('a.xhtml', html('<p id="1x">a</p>'))], ver=2)
        report: list[str] = []
        self.assertFalse(check_and_fix(c, report.append, frozenset({'InvalidId'})))
        self.assertEqual(report, ['No errors found'])
        self.assertIn('id="1x"', self.raw(c, 'a.xhtml'))


def find_tests() -> unittest.TestSuite:
    import unittest

    return unittest.defaultTestLoader.loadTestsFromTestCase(PolishActions)


if __name__ == '__main__':
    from calibre.utils.run_tests import run_cli

    run_cli(find_tests())
