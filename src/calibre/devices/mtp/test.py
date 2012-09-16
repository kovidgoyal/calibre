#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import unittest, gc, io

from calibre.constants import iswindows, islinux
from calibre.utils.icu import lower
from calibre.devices.mtp.driver import MTP_DEVICE
from calibre.devices.scanner import DeviceScanner

class ProgressCallback(object):

    def __init__(self):
        self.count = 0
        self.end_called = False

    def __call__(self, pos, total):
        if pos == total:
            self.end_called = True
        self.count += 1

class TestDeviceInteraction(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.dev = cls.storage = None
        cls.dev = MTP_DEVICE(None)
        cls.dev.startup()
        cls.scanner = DeviceScanner()
        cls.scanner.scan()
        cd = cls.dev.detect_managed_devices(cls.scanner.devices)
        if cd is None:
            cls.dev.shutdown()
            cls.dev = None
            return
        cls.dev.open(cd, 'test_library')
        if cls.dev.free_space()[0] < 10*(1024**2):
            return
        cls.dev.filesystem_cache
        cls.storage = cls.dev.filesystem_cache.entries[0]

    @classmethod
    def tearDownClass(cls):
        if cls.dev is not None:
            cls.dev.shutdown()
            cls.dev = None

    def setUp(self):
        self.cleanup = []

    def tearDown(self):
        for obj in reversed(self.cleanup):
            self.dev.delete_file_or_folder(obj)

    def check_setup(self):
        if self.dev is None:
            self.skipTest('No MTP device detected')
        if self.storage is None:
            self.skipTest('The connected device does not have enough free space')

    def test_folder_operations(self):
        ''' Test the creation of folders, duplicate folders and sub folders '''
        self.check_setup()

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

    def test_file_transfer(self):
        ''' Test transferring files to and from the device '''
        self.check_setup()
        # Create a folder
        name = 'zzz-test-folder'
        folder = self.dev.create_folder(self.storage, name)
        self.cleanup.append(folder)
        self.assertTrue(folder.is_folder)
        self.assertEqual(folder.parent_id, self.storage.object_id)

        # Check simple file put/get
        size = 1024**2
        raw = io.BytesIO(b'a'*size)
        raw.seek(0)
        name = 'test-file.txt'
        pc = ProgressCallback()
        f = self.dev.put_file(folder, name, raw, size, callback=pc)
        self.cleanup.append(f)
        self.assertEqual(f.name, name)
        self.assertEqual(f.size, size)
        self.assertEqual(f.parent_id, folder.object_id)
        self.assertEqual(f.storage_id, folder.storage_id)
        self.assertTrue(pc.end_called,
                msg='Progress callback not called with equal values (put_file)')
        self.assertTrue(pc.count > 1,
                msg='Progress callback only called once (put_file)')

        raw2 = io.BytesIO()
        pc = ProgressCallback()
        self.dev.get_mtp_file(f, raw2, callback=pc)
        self.assertEqual(raw.getvalue(), raw2.getvalue())
        self.assertTrue(pc.end_called,
                msg='Progress callback not called with equal values (get_file)')
        self.assertTrue(pc.count > 1,
                msg='Progress callback only called once (get_file)')

        # Check file replacement
        raw = io.BytesIO(b'abcd')
        raw.seek(0)
        size = 4
        f = self.dev.put_file(folder, name, raw, size)
        self.cleanup.append(f)
        self.assertEqual(f.name, name)
        self.assertEqual(f.size, size)
        self.assertEqual(f.parent_id, folder.object_id)
        self.assertEqual(f.storage_id, folder.storage_id)

        # Check that we get an error with replace=False
        raw.seek(0)
        with self.assertRaises(ValueError):
            self.dev.put_file(folder, name, raw, size, replace=False)

        # Check that we can put a file into the root
        raw.seek(0)
        name = 'zzz-test-file.txt'
        f = self.dev.put_file(self.storage, name, raw, size)
        self.cleanup.append(f)
        self.assertEqual(f.name, name)
        self.assertEqual(f.size, size)
        self.assertEqual(f.parent_id, self.storage.object_id)
        self.assertEqual(f.storage_id, self.storage.storage_id)

        raw2 = io.BytesIO()
        self.dev.get_mtp_file(f, raw2)
        self.assertEqual(raw.getvalue(), raw2.getvalue())

    def measure_memory_usage(self, repetitions, func, *args, **kwargs):
        from calibre.utils.mem import memory
        gc.disable()
        try:
            start_mem = memory()
            for i in xrange(repetitions):
                func(*args, **kwargs)
            for i in xrange(3): gc.collect()
            end_mem = memory()
        finally:
            gc.enable()
        return end_mem - start_mem

    def check_memory(self, once, many, msg, factor=2):
        msg += ' for once: %g for many: %g'%(once, many)
        if once > 0:
            self.assertTrue(many <= once*factor, msg=msg)
        else:
            self.assertTrue(many <= 0.01, msg=msg)

    @unittest.skipUnless(iswindows or islinux, 'Can only test for leaks on windows and linux')
    def test_memory_leaks(self):
        ''' Test for memory leaks in the C module '''
        self.check_setup()

        # Test device scanning
        used_by_one = self.measure_memory_usage(1,
                self.dev.detect_managed_devices, self.scanner.devices,
                force_refresh=True)

        used_by_many = self.measure_memory_usage(100,
                self.dev.detect_managed_devices, self.scanner.devices,
                force_refresh=True)

        self.check_memory(used_by_one, used_by_many,
                'Memory consumption during device scan')

        # Test file transfer
        size = 1024*100
        raw = io.BytesIO(b'a'*size)
        raw.seek(0)
        name = 'zzz-test-file.txt'

        def send_file(storage, name, raw, size):
            raw.seek(0)
            pc = ProgressCallback()
            f = self.dev.put_file(storage, name, raw, size, callback=pc)
            self.cleanup.append(f)
            del pc

        used_once = self.measure_memory_usage(1, send_file, self.storage, name,
                raw, size)
        used_many = self.measure_memory_usage(20, send_file, self.storage, name,
                raw, size)

        self.check_memory(used_once, used_many,
                'Memory consumption during put_file:')

        def get_file(f):
            raw = io.BytesIO()
            pc = ProgressCallback()
            self.dev.get_mtp_file(f, raw, callback=pc)
            raw.truncate(0)
            del raw
            del pc

        f = self.storage.file_named(name)
        used_once = self.measure_memory_usage(1, get_file, f)
        used_many = self.measure_memory_usage(20, get_file, f)
        self.check_memory(used_once, used_many,
                'Memory consumption during get_file:')

        # Test get_filesystem
        used_by_one = self.measure_memory_usage(1,
                self.dev.dev.get_filesystem, self.storage.object_id)

        used_by_many = self.measure_memory_usage(5,
                self.dev.dev.get_filesystem, self.storage.object_id)

        self.check_memory(used_by_one, used_by_many,
                'Memory consumption during get_filesystem')


def tests():
    tl = unittest.TestLoader()
    # return tl.loadTestsFromName('test.TestDeviceInteraction.test_memory_leaks')
    return tl.loadTestsFromTestCase(TestDeviceInteraction)

def run():
    unittest.TextTestRunner(verbosity=2).run(tests())

if __name__ == '__main__':
    run()

