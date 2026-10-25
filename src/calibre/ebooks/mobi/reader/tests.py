#!/usr/bin/env python
# License: GPLv3 Copyright: 2026

import unittest
from types import SimpleNamespace

from calibre.ebooks.mobi.reader.markup import update_flow_links


class Log:
    def __init__(self):
        self.warnings = []

    def warn(self, message):
        self.warnings.append(message)


class TestMarkup(unittest.TestCase):
    def test_kindle_embed_font_urls(self):
        urls = (
            'url(kindle:embed:0001?mime=application/x-font-ttf)',
            'url("kindle:embed:0001?mime=application/x-font-ttf")',
            "url('kindle:embed:0001?mime=application/x-font-ttf')",
            'url(kindle:embed:0001)',
        )
        expected = 'url("../fonts/00003.ttf")'
        for url in urls:
            with self.subTest(url=url):
                reader = SimpleNamespace(flows=[None, f'@font-face {{ src: {url}; }}'], flowinfo=[])
                log = Log()
                flows = update_flow_links(reader, ['fonts/00003.ttf'], log)
                self.assertEqual(flows[1], f'@font-face {{ src: {expected}; }}')
                self.assertEqual(log.warnings, [])

    def test_missing_kindle_embed_font_is_preserved_and_warned(self):
        url = 'url("kindle:embed:0001?mime=application/x-font-ttf")'
        reader = SimpleNamespace(flows=[None, f'@font-face {{ src: {url}; }}'], flowinfo=[])
        log = Log()
        flows = update_flow_links(reader, [None], log)
        self.assertIn(url, flows[1])
        self.assertEqual(len(log.warnings), 1)
        self.assertIn('Referenced font 1', log.warnings[0])

    def test_failed_kindle_embed_font_keeps_broken_resource_path(self):
        reader = SimpleNamespace(flows=[None, '@font-face { src: url(kindle:embed:0001); }'], flowinfo=[])
        flows = update_flow_links(reader, ['fonts/00003.ttf.failed'], Log())
        self.assertIn('url("failed-fonts/00003.ttf.failed")', flows[1])


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestMarkup)
