#!/usr/bin/env python
# License: GPLv3 Copyright: 2010, Kovid Goyal <kovid@kovidgoyal.net>

import io
import os
from contextlib import closing
from posixpath import basename
from typing import IO, TYPE_CHECKING, cast

from calibre.customize import FileTypePlugin
from calibre.utils.localization import _, canonicalize_lang

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import TypedDict

    from calibre.ebooks.metadata.book.base import Metadata

    class ComicBookInfoCredit(TypedDict, total=False):
        person: str
        role: str
        primary: bool

    class ComicBookInfo(TypedDict, total=False):
        """See https://code.google.com/archive/p/comicbookinfo/wikis/Example.wiki"""

        series: str
        title: str
        publisher: str
        publicationMonth: int
        publicationYear: int
        issue: int
        numberOfIssues: int
        volume: int
        numberOfVolumes: int
        rating: float
        genre: str
        language: str
        country: str
        credits: list[ComicBookInfoCredit]
        tags: list[str]
        comments: str


def is_comic(list_of_names: Iterable[str]) -> bool:
    extensions = {x.rpartition('.')[-1].lower() for x in list_of_names if '.' in x and x.lower().rpartition('/')[-1] != 'thumbs.db'}
    comic_extensions = {'jpg', 'jpeg', 'png'}
    return len(extensions - comic_extensions) == 0


def archive_type(stream: IO[bytes]) -> str | None:
    from calibre.utils.zipfile import stringFileHeader

    try:
        pos = stream.tell()
    except Exception:
        pos = 0
    id_ = stream.read(4)
    ans = None
    if id_ == stringFileHeader:
        ans = 'zip'
    elif id_.startswith(b'Rar'):
        ans = 'rar'
    try:
        stream.seek(pos)
    except Exception:
        pass
    return ans


class KPFExtract(FileTypePlugin):
    name = 'KPF Extract'
    author = 'Kovid Goyal'
    description = _(
        'Extract the source DOCX file from Amazon Kindle Create KPF files. Note this will not contain any edits made in the Kindle Create program itself.'
    )
    file_types = {'kpf'}
    supported_platforms = ['windows', 'osx', 'linux']
    on_import = True

    def run(self, path_to_ebook: str) -> str:
        from calibre.utils.zipfile import ZipFile

        with ZipFile(path_to_ebook, 'r') as zf:
            fnames = zf.namelist()
            candidates = [x for x in fnames if x.lower().endswith('.docx')]
            if not candidates:
                return path_to_ebook
            of = self.temporary_file('_kpf_extract.docx')
            with closing(of):
                of.write(zf.read(candidates[0]))
        return of.name


class RAR:
    def __init__(self, archive: str | IO[bytes]) -> None:
        self.archive = archive

    def close(self) -> None:
        pass

    def namelist(self) -> list[str]:
        from calibre.utils.unrar import names

        return list(names(self.archive))

    def read(self, fname: str) -> bytes:
        from calibre.utils.unrar import extract_member

        res = extract_member(self.archive, match=None, name=fname)
        if res is None:
            raise KeyError(f'There is no file named {fname} in the archive')
        return res[1]


class SevenZip:
    def __init__(self, archive: str | IO[bytes]) -> None:
        from py7zr import SevenZipFile

        self.zf = SevenZipFile(archive, 'r')

    def namelist(self) -> list[str]:
        return list(self.zf.getnames())

    def close(self) -> None:
        self.zf.close()

    def read(self, fname: str) -> bytes:
        from py7zr import WriterFactory

        class MemoryFactory(WriterFactory):
            def __init__(self) -> None:
                self.buffers: dict[str, io.BytesIO] = {}

            def create(self, filename: str) -> io.BytesIO:  # ty: ignore[invalid-method-override] BytesIO is duck type compatible with Py7zIO
                # Create an in-memory BytesIO stream for the file
                self.buffers[filename] = io.BytesIO()
                return self.buffers[filename]

        factory = MemoryFactory()
        self.zf.extract(targets=[fname], factory=factory)
        target_buffer: io.BytesIO = factory.buffers[fname]
        target_buffer.seek(0)
        return target_buffer.getvalue()


def fname_ok(fname: str) -> bool:
    fname = fname.replace('\\', '/')
    bn = basename(fname).lower()
    if bn == 'thumbs.db':
        return False
    if '.' not in bn:
        return False
    if bn.rpartition('.')[-1] in {'diz', 'nfo'}:
        return False
    if '__MACOSX' in fname.split('/'):
        return False
    return True


class ArchiveExtract(FileTypePlugin):
    name = 'Archive Extract'
    author = 'Kovid Goyal'
    description = _('Extract common e-book formats from archive files (ZIP/RAR/7z). Also try to autodetect if they are actually CBZ/CBR/CB7 files.')
    file_types = {'zip', 'rar', '7z'}
    supported_platforms = ['windows', 'osx', 'linux']
    on_import = True

    def run(self, path_to_ebook: str) -> str:
        import shutil

        q = path_to_ebook.lower()
        if q.endswith('.rar'):
            comic_ext = 'cbr'
            zf = RAR(path_to_ebook)
        elif q.endswith('.7z'):
            comic_ext = 'cb7'
            zf = SevenZip(path_to_ebook)
        else:
            from calibre.utils.zipfile import ZipFile

            zf = ZipFile(path_to_ebook, 'r')
            comic_ext = 'cbz'

        with closing(zf):
            fnames = zf.namelist()
            fnames = list(filter(fname_ok, fnames))
            if is_comic(fnames):
                of = self.temporary_file('_archive_extract.' + comic_ext)
                with closing(of), open(path_to_ebook, 'rb') as f:
                    shutil.copyfileobj(f, of)
                return of.name
            if len(fnames) > 1 or not fnames:
                return path_to_ebook
            fname = fnames[0]
            ext = os.path.splitext(fname)[1][1:]
            if ext.lower() not in {
                'lit',
                'txt',
                'md',
                'markdown',
                'epub',
                'mobi',
                'prc',
                'rtf',
                'pdf',
                'mp3',
                'pdb',
                'azw',
                'azw1',
                'azw3',
                'fb2',
                'docx',
                'doc',
                'odt',
            }:
                return path_to_ebook

            of = self.temporary_file('_archive_extract.' + ext)
            with closing(of):
                of.write(zf.read(fname))
            return of.name


def get_comic_book_info(d: ComicBookInfo, mi: Metadata, series_index: str = 'volume') -> None:
    # See http://code.google.com/p/comicbookinfo/wiki/Example
    series = d.get('series', '')
    if series.strip():
        mi.series = series
        si = d.get(series_index, None)
        if si is None:
            si = d.get('issue' if series_index == 'volume' else 'volume', None)
        if si is not None:
            try:
                mi.series_index = float(si)
            except Exception:
                mi.series_index = 1
    if d.get('language', None):
        lang = canonicalize_lang(d.get('language'))
        if lang:
            mi.languages = [lang]
    if d.get('rating', -1) > -1:
        mi.rating = d['rating']
    for x in ('title', 'publisher'):
        y = d.get(x, '').strip()
        if y:
            setattr(mi, x, y)
    tags = d.get('tags', [])
    if tags:
        mi.tags = tags
    authors: list[str] = []
    for credit in d.get('credits', []):
        if credit.get('role', '') in ('Writer', 'Artist', 'Cartoonist', 'Creator'):
            x = credit.get('person', '')
            if x:
                x = ' '.join(reversed(x.split(', ')))
                authors.append(x)
    if authors:
        mi.authors = authors
    comments = d.get('comments', '')
    if comments and comments.strip():
        mi.comments = comments.strip()
    pubm, puby = d.get('publicationMonth', None), d.get('publicationYear', None)
    if puby is not None:
        from datetime import date

        from calibre.utils.date import parse_only_date

        try:
            dt = date(puby, 6 if pubm is None else pubm, 15)
            dt = parse_only_date(str(dt))
            mi.pubdate = dt
        except Exception:
            pass


def parse_comic_comment(comment: str | bytes, series_index: str = 'volume') -> Metadata:
    # See http://code.google.com/p/comicbookinfo/wiki/Example
    import json

    from calibre.ebooks.metadata import MetaInformation

    mi = MetaInformation(None, None)
    m = json.loads(comment)
    if isinstance(m, dict):
        for cat in m:
            if cat.startswith('ComicBookInfo'):
                get_comic_book_info(m[cat], mi, series_index=series_index)
                break
    return mi


def get_comic_metadata(stream: IO[bytes], stream_type: str, series_index: str = 'volume') -> Metadata:
    comment = None
    if stream_type == 'cbz':
        from calibre.utils.zipfile import ZipFile

        zf = ZipFile(stream)
        comment = zf.comment
    elif stream_type == 'cbr':
        from calibre.utils.unrar import comment as get_comment

        comment = get_comment(stream)

    return parse_comic_comment(comment or b'{}', series_index=series_index)


def get_comic_images(path: str, tdir: str, first: int = 1, last: int = 0) -> int:  # first and last use 1 based indexing
    from functools import partial

    with open(path, 'rb') as f:
        fmt = archive_type(f)
        if fmt not in ('zip', 'rar'):
            return 0
    items: dict = {}
    if fmt == 'rar':
        from calibre.utils.unrar import headers

        for h in headers(path):
            items[h['filename']] = partial(h.get, 'file_time', 0)
    else:
        from zipfile import ZipFile

        with ZipFile(path) as zf:
            for i in zf.infolist():
                items[i.filename] = partial(getattr, i, 'date_time')
    from calibre.ebooks.comic.input import find_pages

    pages = find_pages(items)
    if last <= 0:
        last = len(pages)
    pages = pages[first - 1 : last]

    def make_filename(num: int, ext: str) -> str:
        return f'{num:08d}{ext}'

    if fmt == 'rar':
        all_pages = {p: i + first for i, p in enumerate(pages)}
        from calibre.utils.unrar import extract_members

        current = None

        def callback(x: dict[str, object] | bytes | bool) -> bool | None:
            nonlocal current
            if isinstance(x, dict):
                if current is not None:
                    current.close()
                fname = cast('str', x['filename'])  # the filename in an unrar header is a str
                if fname in all_pages:
                    ext = os.path.splitext(fname)[1]
                    num = all_pages[fname]
                    current = open(os.path.join(tdir, make_filename(num, ext)), 'wb')  # ruff: ignore[open-file-with-context-handler]
                    return True
                return False
            if isinstance(x, bytes):
                assert current is not None
                current.write(x)

        extract_members(path, callback)
        if current is not None:
            current.close()
    else:
        import shutil

        with ZipFile(path) as zf:
            for i, name in enumerate(pages):
                num = i + first
                ext = os.path.splitext(name)[1]
                with open(os.path.join(tdir, make_filename(num, ext)), 'wb') as dest, zf.open(name) as src:
                    shutil.copyfileobj(src, dest)
    return len(pages)
