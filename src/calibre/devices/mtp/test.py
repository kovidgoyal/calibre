#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import unittest

from calibre.constants import iswindows, islinux
from calibre.utils.icu import lower
from calibre.devices.mtp.driver import MTP_DEVICE
from calibre.devices.scanner import DeviceScanner

class TestDeviceInteraction(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.dev = MTP_DEVICE(None)
        cls.dev.startup()
        cls.scanner = DeviceScanner()
        cls.scanner.scan()
        cd = cls.dev.detect_managed_devices(cls.scanner.devices)
        if cd is None:
            raise ValueError('No MTP device found')
        cls.dev.open(cd, 'test_library')
        if cls.dev.free_space()[0] < 10*(1024**2):
            raise ValueError('The connected device %s does not have enough free'
                    ' space in its main memory to do the tests'%cd)
        cls.dev.filesystem_cache
        cls.storage = cls.dev.filesystem_cache.entries[0]

    @classmethod
    def tearDownClass(cls):
        cls.dev.shutdown()
        cls.dev = None

    def setUp(self):
        self.cleanup = []

    def tearDown(self):
        for obj in reversed(self.cleanup):
            self.dev.delete_file_or_folder(obj)

    def test_folder_operations(self):
        ''' Test the creation of folders, duplicate folders and sub folders '''

        # Create a folder
        name = 'zzz-test-folder'
        folder = self.dev.create_folder(self.storage, name)
        self.cleanup.append(folder)
        self.assertTrue(folder.is_folder)
        self.assertEqual(folder.parent_id, self.storage.object_id)
        self.assertEqual(folder.storage_id, self.storage.object_id)
        self.assertEqual(lower(name), lower(folder.name))

        # Create a sub-folder
        name = 'sub-folder'
        subfolder = self.dev.create_folder(folder, name)
        self.assertTrue(subfolder.is_folder)
        self.assertEqual(subfolder.parent_id, folder.object_id)
        self.assertEqual(subfolder.storage_id, self.storage.object_id)
        self.assertEqual(lower(name), lower(subfolder.name))
        self.cleanup.append(subfolder)

        # Check that creating an existing folder returns that folder (case
        # insensitively)
        self.assertIs(subfolder, self.dev.create_folder(folder,
            'SUB-FOLDER'),
            msg='Creating an existing folder did not return the existing folder')

        # Check that creating folders as children of files is not allowed
        root_file = [f for f in self.dev.filesystem_cache.entries[0].files if
                not f.is_folder]
        if root_file:
            with self.assertRaises(ValueError):
                self.dev.create_folder(root_file[0], 'sub-folder')

    def test_memory_leaks(self):
        if not (iswindows or islinux):
            self.skipTest('Can only test for leaks on windows and linux')
        from calibre.utils.mem import memory

def tests():
    return unittest.TestLoader().loadTestsFromTestCase(TestDeviceInteraction)

def run():
    unittest.TextTestRunner(verbosity=2).run(tests())

if __name__ == '__main__':
    run()

