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

    def test_remove_unused_images(self) -> None:
        self.assert_cli_option('--remove-unused-images', 'remove_unused_images')
        c = self.create_epub([cmi('a.html', html('<img src="used.png" alt="u"/>')), cmi('used.png'), cmi('unused.png')])
        changed, report = self.polish(c, remove_unused_images=True)
        self.assertTrue(changed)
        self.assertIn('used.png', c.mime_map)
        self.assertNotIn('unused.png', c.mime_map)
        self.assertFalse(self.polish(c, remove_unused_images=True)[0])


def find_tests() -> unittest.TestSuite:
    import unittest

    return unittest.defaultTestLoader.loadTestsFromTestCase(PolishActions)


if __name__ == '__main__':
    from calibre.utils.run_tests import run_cli

    run_cli(find_tests())
