#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, maskshell fork
'''Markdown toc extension must emit short, HTML-valid heading ids.'''

from __future__ import annotations

import re
import unittest

from calibre.ebooks.oeb.polish.tests.base import BaseTest
from calibre.ebooks.txt.processor import convert_markdown, short_valid_toc_slugify


class MarkdownTocIdTests(BaseTest):
    def test_short_valid_toc_slugify(self) -> None:
        self.assertEqual(short_valid_toc_slugify('第7章 被群灭的不良们', '-'), 'id7')
        self.assertEqual(short_valid_toc_slugify('第一卷', '-'), 'id')
        self.assertEqual(short_valid_toc_slugify('Chapter 7 Hello', '-'), 'chapter-7-hello')
        self.assertRegex(short_valid_toc_slugify('7', '-'), r'^[A-Za-z]')

    def test_markdown_chinese_headings_get_valid_short_ids(self) -> None:
        html = convert_markdown('## 第一卷\n\n### 第1章 黄山\n\npara\n\n### 第2章 测试\n\npara2\n')
        ids = re.findall(r'<h[23] id="([^"]+)"', html)
        self.assertEqual(len(ids), 3)
        for eid in ids:
            self.assertRegex(eid, r'^[A-Za-z][A-Za-z0-9_-]*$', msg=eid)
            self.assertLessEqual(len(eid), 24, msg=eid)
        self.assertEqual(len(set(ids)), 3)
        self.assertTrue(all(len(e) <= 8 for e in ids))


if __name__ == '__main__':
    unittest.main(verbosity=2)
