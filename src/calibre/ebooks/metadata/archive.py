#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import textwrap, os
from contextlib import closing

from calibre.customize import FileTypePlugin

class ArchiveExtract(FileTypePlugin):
    name = 'Archive Extract'
    author = 'Kovid Goyal'
    description = textwrap.dedent(_('''\
        Extract common e-book formats from archives (zip/rar) files.
    '''))
    file_types = set(['zip', 'rar'])
    supported_platforms = ['windows', 'osx', 'linux']
    on_import = True

    def run(self, archive):
        is_rar = archive.lower().endswith('.rar')
        if is_rar:
            from calibre.libunrar import extract_member, names
        else:
            from calibre.utils.zipfile import ZipFile
            zf = ZipFile(archive, 'r')

        if is_rar:
            fnames = names(archive)
        else:
            fnames = zf.namelist()

        fnames = [x for x in fnames if '.' in x]
        if len(fnames) > 1 or not fnames:
            return archive
        fname = fnames[0]
        ext = os.path.splitext(fname)[1][1:]
        if ext.lower() not in ('lit', 'epub', 'mobi', 'prc', 'rtf', 'pdf',
                'mp3'):
            return archive

        of = self.temporary_file('_archive_extract.'+ext)
        with closing(of):
            if is_rar:
                data = extract_member(archive, match=None, name=fname)[1]
                of.write(data)
            else:
                of.write(zf.read(fname))
        return of.name

