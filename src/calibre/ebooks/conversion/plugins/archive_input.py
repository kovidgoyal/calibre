#!/usr/bin/env python


__license__   = 'GPL 3'
__copyright__ = '2026, Hassan Raza <raihassanraza10 at gmail.com>'
__docformat__ = 'restructuredtext en'


def path_in_archive_root(root, path):
    ' Resolve a path from archive metadata, returning None if it leaves root. '
    import os

    from calibre.utils.filenames import is_path_inside, path_from_root
    if isinstance(path, str) and os.path.isabs(path):
        if is_path_inside(root, path):
            return os.path.abspath(path)
    else:
        try:
            return path_from_root(root, path)
        except ValueError:
            pass


def archive_file_data(root, path):
    path = path_in_archive_root(root, path)
    if path is not None:
        import os
        if os.path.isfile(path):
            with open(path, 'rb') as f:
                return os.path.basename(path), f.read()


def find_tests():
    import os
    import tempfile
    import unittest

    class ArchiveInputTest(unittest.TestCase):

        def test_archive_file_data(self):
            with tempfile.TemporaryDirectory() as tdir:
                root = os.path.abspath(tdir)
                os.mkdir(os.path.join(root, 'images'))
                with open(os.path.join(root, 'images', 'cover.jpg'), 'wb') as f:
                    f.write(b'cover')
                sibling = root + ' sibling'
                os.mkdir(sibling)
                with open(os.path.join(sibling, 'cover.jpg'), 'wb') as f:
                    f.write(b'outside')

                self.assertEqual(archive_file_data(root, 'images/cover.jpg'), ('cover.jpg', b'cover'))
                self.assertEqual(
                    archive_file_data(root, os.path.join(root, 'images', 'cover.jpg')), ('cover.jpg', b'cover'))
                self.assertEqual(archive_file_data(root, r'images\cover.jpg'), ('cover.jpg', b'cover'))
                for path in ('images/missing.jpg', '../' + os.path.basename(sibling) + '/cover.jpg',
                             '/cover.jpg', 'C:/cover.jpg', 'C:cover.jpg'):
                    self.assertIsNone(archive_file_data(root, path))

    return unittest.defaultTestLoader.loadTestsFromTestCase(ArchiveInputTest)


if __name__ == '__main__':
    from calibre.utils.run_tests import run_tests
    run_tests(find_tests)
