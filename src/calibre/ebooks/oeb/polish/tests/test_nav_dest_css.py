#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, maskshell fork
'''Stylesheet link elements must not raise BadDestinationType.'''

from __future__ import annotations

import os
import unittest

from calibre.ebooks.oeb.polish.check.links import BadDestinationType, check_links
from calibre.ebooks.oeb.polish.container import get_container
from calibre.ebooks.oeb.polish.tests.base import BaseTest
from calibre.ebooks.oeb.polish.tests.structure import cmi, create_epub


class NavDestinationCssTests(BaseTest):
    def test_stylesheet_link_not_bad_destination_type(self) -> None:
        html = (
            '<html xmlns="http://www.w3.org/1999/xhtml"><head>'
            '<link rel="stylesheet" type="text/css" href="stylesheet.css"/>'
            '<link rel="stylesheet" type="text/css" href="page_styles.css"/>'
            '</head><body>'
            '<p><a href="stylesheet.css">bad nav to css</a></p>'
            '<p><a href="cover.jpeg">bad nav to image</a></p>'
            '<p>ok</p></body></html>'
        )
        ep = os.path.join(self.tdir, 'nav-dest.epub')
        with open(ep, 'wb') as f:
            f.write(
                create_epub(
                    [
                        cmi('index.html', html),
                        cmi('stylesheet.css', 'p { margin: 0 }'),
                        cmi('page_styles.css', '@page { margin: 0 }'),
                        cmi('cover.jpeg', b'\xff\xd8\xff\xd9'),
                    ]
                ).getvalue()
            )
        c = get_container(ep, tdir=os.path.join(self.tdir, 'nav-dest-c'), tweak_mode=True)
        errors = check_links(c)
        bad = [e for e in errors if isinstance(e, BadDestinationType)]
        hrefs = sorted(e.bad_href for e in bad)
        self.assertEqual(hrefs, ['cover.jpeg', 'stylesheet.css'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
