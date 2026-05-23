#!/usr/bin/env python


__license__   = 'GPL 3'
__copyright__ = '2026, Hassan Raza <raihassanraza10 at gmail.com>'
__docformat__ = 'restructuredtext en'


def path_in_archive_root(root, path):
    ' Resolve a path from archive metadata, returning None if it leaves root. '
    from calibre.utils.filenames import path_from_root
    try:
        return path_from_root(root, path)
    except ValueError:
        return None


def archive_file_data(root, path):
    path = path_in_archive_root(root, path)
    if path is not None:
        import os
        if os.path.isfile(path):
            with open(path, 'rb') as f:
                return os.path.basename(path), f.read()
