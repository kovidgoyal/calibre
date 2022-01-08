#!/usr/bin/env python
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>


import os
import unittest


class TestWinutil(unittest.TestCase):

    def setUp(self):
        from calibre_extensions import winutil
        self.winutil = winutil

    def tearDown(self):
        del self.winutil

    def test_add_to_recent_docs(self):
        path = str(os.path.abspath(__file__))
        self.winutil.add_to_recent_docs(path, None)
        self.winutil.add_to_recent_docs(path, 'some-app-uid')

    def test_file_association(self):
        q = self.winutil.file_association('.txt')
        self.assertIn('notepad.exe', q.lower())
        self.assertNotIn('\0', q)
        q = self.winutil.friendly_name(None, 'notepad.exe')
        self.assertEqual('Notepad', q)

    def test_special_folder_path(self):
        self.assertEqual(os.path.expanduser('~'), self.winutil.special_folder_path(self.winutil.CSIDL_PROFILE))

    def test_associations_changed(self):
        self.assertIsNone(self.winutil.notify_associations_changed())


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestWinutil)
