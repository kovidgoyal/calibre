#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

import os
import re
import unittest

from lxml.html import fromstring, tostring

from calibre.utils.resources import get_path as P

from .simple import Overseer

skip = ''
is_sanitized = 'libasan' in os.environ.get('LD_PRELOAD', '')
if is_sanitized:
    skip = 'Skipping Scraper tests as ASAN is enabled'
elif 'SKIP_QT_BUILD_TEST' in os.environ:
    skip = 'Skipping Scraper tests as it causes crashes in macOS VM'


@unittest.skipIf(skip, skip)
class TestSimpleWebEngineScraper(unittest.TestCase):

    def test_dom_load(self):
        from qt.core import QUrl
        overseer = Overseer()
        for f in ('book', 'nav'):
            path = P(f'templates/new_{f}.html', allow_user_override=False)
            url = QUrl.fromLocalFile(path)
            html = overseer.fetch_url(url, 'test')

            def c(a):
                ans = tostring(fromstring(a.encode('utf-8')), pretty_print=True, encoding='unicode')
                return re.sub(r'\s+', ' ', ans)
            with open(path, 'rb') as f:
                raw = f.read().decode('utf-8')
            self.assertEqual(c(html), c(raw))
        self.assertRaises(ValueError, overseer.fetch_url, 'file:///does-not-exist.html', 'test')
        w = overseer.workers
        self.assertEqual(len(w), 1)
        del overseer
        self.assertFalse(w)


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestSimpleWebEngineScraper)
