#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from contextlib import closing

from calibre.customize import FileTypePlugin
from calibre.utils.zipfile import ZipFile, stringFileHeader

def is_comic(list_of_names):
    extensions = set([x.rpartition('.')[-1].lower() for x in list_of_names])
    comic_extensions = set(['jpg', 'jpeg', 'png'])
    return len(extensions - comic_extensions) == 0

def archive_type(stream):
    try:
        pos = stream.tell()
    except:
        pos = 0
    id_ = stream.read(4)
    ans = None
    if id_ == stringFileHeader:
        ans = 'zip'
    elif id_.startswith('Rar'):
        ans = 'rar'
    try:
        stream.seek(pos)
    except:
        pass
    return ans


class ArchiveExtract(FileTypePlugin):
    name = 'Archive Extract'
    author = 'Kovid Goyal'
    description = _('Extract common e-book formats from archives '
        '(zip/rar) files. Also try to autodetect if they are actually '
        'cbz/cbr files.')
    file_types = set(['zip', 'rar'])
    supported_platforms = ['windows', 'osx', 'linux']
    on_import = True

    def run(self, archive):
        is_rar = archive.lower().endswith('.rar')
        if is_rar:
            from calibre.utils.unrar import extract_member, names
        else:
            zf = ZipFile(archive, 'r')

        if is_rar:
            with open(archive, 'rb') as rf:
                fnames = list(names(rf))
        else:
            fnames = zf.namelist()

        fnames = [x for x in fnames if '.' in x]
        if is_comic(fnames):
            ext = '.cbr' if is_rar else '.cbz'
            of = self.temporary_file('_archive_extract'+ext)
            with open(archive, 'rb') as f:
                of.write(f.read())
            of.close()
            return of.name
        if len(fnames) > 1 or not fnames:
            return archive
        fname = fnames[0]
        ext = os.path.splitext(fname)[1][1:]
        if ext.lower() not in ('lit', 'epub', 'mobi', 'prc', 'rtf', 'pdf',
                'mp3', 'pdb', 'azw', 'azw1', 'azw3', 'fb2'):
            return archive

        of = self.temporary_file('_archive_extract.'+ext)
        with closing(of):
            if is_rar:
                with open(archive, 'rb') as f:
                    data = extract_member(f, match=None, name=fname)[1]
                of.write(data)
            else:
                of.write(zf.read(fname))
        return of.name

def get_comic_book_info(d, mi):
    # See http://code.google.com/p/comicbookinfo/wiki/Example
    series = d.get('series', '')
    if series.strip():
        mi.series = series
        if d.get('volume', -1) > -1:
            mi.series_index = float(d['volume'])
    if d.get('rating', -1) > -1:
        mi.rating = d['rating']
    for x in ('title', 'publisher'):
        y = d.get(x, '').strip()
        if y:
            setattr(mi, x, y)
    tags = d.get('tags', [])
    if tags:
        mi.tags = tags
    authors = []
    for credit in d.get('credits', []):
        if credit.get('role', '') in ('Writer', 'Artist', 'Cartoonist',
                'Creator'):
            x = credit.get('person', '')
            if x:
                x = ' '.join((reversed(x.split(', '))))
                authors.append(x)
    if authors:
        mi.authors = authors
    comments = d.get('comments', '')
    if comments and comments.strip():
        mi.comments = comments.strip()
    pubm, puby = d.get('publicationMonth', None), d.get('publicationYear', None)
    if puby is not None:
        from calibre.utils.date import parse_only_date
        from datetime import date
        try:
            dt = date(puby, 6 if pubm is None else pubm, 15)
            dt = parse_only_date(str(dt))
            mi.pubdate = dt
        except:
            pass

def get_comic_metadata(stream, stream_type):
    # See http://code.google.com/p/comicbookinfo/wiki/Example
    from calibre.ebooks.metadata import MetaInformation

    comment = None

    mi = MetaInformation(None, None)

    if stream_type == 'cbz':
        from calibre.utils.zipfile import ZipFile
        zf = ZipFile(stream)
        comment = zf.comment
    elif stream_type == 'cbr':
        from calibre.utils.unrar import RARFile
        f = RARFile(stream, get_comment=True)
        comment = f.comment

    if comment:
        import json
        m = json.loads(comment)
        if hasattr(m, 'iterkeys'):
            for cat in m.iterkeys():
                if cat.startswith('ComicBookInfo'):
                    get_comic_book_info(m[cat], mi)
                    break
    return mi

