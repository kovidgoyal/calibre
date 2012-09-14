from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import os, re, collections

from calibre.utils.config import prefs
from calibre.constants import filesystem_encoding
from calibre.ebooks.metadata.opf2 import OPF
from calibre import isbytestring
from calibre.customize.ui import get_file_type_metadata, set_file_type_metadata
from calibre.ebooks.metadata import MetaInformation, string_to_authors

_METADATA_PRIORITIES = [
                       'html', 'htm', 'xhtml', 'xhtm',
                       'rtf', 'fb2', 'pdf', 'prc', 'odt',
                       'epub', 'lit', 'lrx', 'lrf', 'mobi',
                       'rb', 'imp', 'azw', 'azw3', 'azw1' 'snb'
                      ]

# The priorities for loading metadata from different file types
# Higher values should be used to update metadata from lower values
METADATA_PRIORITIES = collections.defaultdict(lambda:0)
for i, ext in enumerate(_METADATA_PRIORITIES):
    METADATA_PRIORITIES[ext] = i

def path_to_ext(path):
    return os.path.splitext(path)[1][1:].lower()

def metadata_from_formats(formats, force_read_metadata=False, pattern=None):
    try:
        return _metadata_from_formats(formats, force_read_metadata, pattern)
    except:
        mi = metadata_from_filename(list(iter(formats))[0], pat=pattern)
        if not mi.authors:
            mi.authors = [_('Unknown')]
        return mi

def _metadata_from_formats(formats, force_read_metadata=False, pattern=None):
    mi = MetaInformation(None, None)
    formats.sort(cmp=lambda x,y: cmp(METADATA_PRIORITIES[path_to_ext(x)],
                                     METADATA_PRIORITIES[path_to_ext(y)]))
    extensions = list(map(path_to_ext, formats))
    if 'opf' in extensions:
        opf = formats[extensions.index('opf')]
        mi2 = opf_metadata(opf)
        if mi2 is not None and mi2.title:
            return mi2

    for path, ext in zip(formats, extensions):
        with open(path, 'rb') as stream:
            try:
                newmi = get_metadata(stream, stream_type=ext,
                                     use_libprs_metadata=True,
                                     force_read_metadata=force_read_metadata,
                                     pattern=pattern)
                mi.smart_update(newmi)
            except:
                continue
            if getattr(mi, 'application_id', None) is not None:
                return mi

    if not mi.title:
        mi.title = _('Unknown')
    if not mi.authors:
        mi.authors = [_('Unknown')]

    return mi

def get_metadata(stream, stream_type='lrf', use_libprs_metadata=False,
                 force_read_metadata=False, pattern=None):
    pos = 0
    if hasattr(stream, 'tell'):
        pos = stream.tell()
    try:
        return _get_metadata(stream, stream_type, use_libprs_metadata,
                             force_read_metadata, pattern)
    finally:
        if hasattr(stream, 'seek'):
            stream.seek(pos)


def _get_metadata(stream, stream_type, use_libprs_metadata,
                  force_read_metadata=False, pattern=None):
    if stream_type: stream_type = stream_type.lower()
    if stream_type in ('html', 'html', 'xhtml', 'xhtm', 'xml'):
        stream_type = 'html'
    if stream_type in ('mobi', 'prc', 'azw', 'azw1', 'azw3'):
        stream_type = 'mobi'
    if stream_type in ('odt', 'ods', 'odp', 'odg', 'odf'):
        stream_type = 'odt'

    opf = None
    if hasattr(stream, 'name'):
        c = os.path.splitext(stream.name)[0]+'.opf'
        if os.access(c, os.R_OK):
            opf = opf_metadata(os.path.abspath(c))

    if use_libprs_metadata and getattr(opf, 'application_id', None) is not None:
        return opf

    mi = MetaInformation(None, None)
    name = os.path.basename(getattr(stream, 'name', ''))
    base = metadata_from_filename(name, pat=pattern)
    if force_read_metadata or prefs['read_file_metadata']:
        mi = get_file_type_metadata(stream, stream_type)
    if base.title == os.path.splitext(name)[0] and \
            base.is_null('authors') and base.is_null('isbn'):
        # Assume that there was no metadata in the file and the user set pattern
        # to match meta info from the file name did not match.
        # The regex is meant to match the standard format filenames are written
        # in: title_-_author_number.extension
        base.smart_update(metadata_from_filename(name, re.compile(
                    r'^(?P<title>[ \S]+?)[ _]-[ _](?P<author>[ \S]+?)_+\d+')))
        if base.title:
            base.title = base.title.replace('_', ' ')
        if base.authors:
            base.authors = [a.replace('_', ' ').strip() for a in base.authors]
    if not base.authors:
        base.authors = [_('Unknown')]
    if not base.title:
        base.title = _('Unknown')
    base.smart_update(mi)
    if opf is not None:
        base.smart_update(opf)

    return base

def set_metadata(stream, mi, stream_type='lrf'):
    if stream_type:
        stream_type = stream_type.lower()
    set_file_type_metadata(stream, mi, stream_type)


def metadata_from_filename(name, pat=None):
    if isbytestring(name):
        name = name.decode(filesystem_encoding, 'replace')
    name = name.rpartition('.')[0]
    mi = MetaInformation(None, None)
    if pat is None:
        pat = re.compile(prefs.get('filename_pattern'))
    name = name.replace('_', ' ')
    match = pat.search(name)
    if match is not None:
        try:
            mi.title = match.group('title')
        except IndexError:
            pass
        try:
            au = match.group('author')
            aus = string_to_authors(au)
            if aus:
                mi.authors = aus
                if prefs['swap_author_names'] and mi.authors:
                    def swap(a):
                        if ',' in a:
                            parts = a.split(',', 1)
                        else:
                            parts = a.split(None, 1)
                        if len(parts) > 1:
                            t = parts[-1]
                            parts = parts[:-1]
                            parts.insert(0, t)
                        return ' '.join(parts)
                    mi.authors = [swap(x) for x in mi.authors]
        except (IndexError, ValueError):
            pass
        try:
            mi.series = match.group('series')
        except IndexError:
            pass
        try:
            si = match.group('series_index')
            mi.series_index = float(si)
        except (IndexError, ValueError, TypeError):
            pass
        try:
            si = match.group('isbn')
            mi.isbn = si
        except (IndexError, ValueError):
            pass
        try:
            publisher = match.group('publisher')
            mi.publisher = publisher
        except (IndexError, ValueError):
            pass
        try:
            pubdate = match.group('published')
            if pubdate:
                from calibre.utils.date import parse_date
                mi.pubdate = parse_date(pubdate)
        except:
            pass

    if mi.is_null('title'):
        mi.title = name
    return mi

def opf_metadata(opfpath):
    if hasattr(opfpath, 'read'):
        f = opfpath
        opfpath = getattr(f, 'name', os.getcwdu())
    else:
        f = open(opfpath, 'rb')
    try:
        opf = OPF(f, os.path.dirname(opfpath))
        if opf.application_id is not None:
            mi = opf.to_book_metadata()
            if hasattr(opf, 'cover') and opf.cover:
                cpath = os.path.join(os.path.dirname(opfpath), opf.cover)
                if os.access(cpath, os.R_OK):
                    fmt = cpath.rpartition('.')[-1]
                    data = open(cpath, 'rb').read()
                    mi.cover_data = (fmt, data)
            return mi
    except:
        import traceback
        traceback.print_exc()
        pass

def forked_read_metadata(path, tdir):
    from calibre.ebooks.metadata.opf2 import metadata_to_opf
    with open(path, 'rb') as f:
        fmt = os.path.splitext(path)[1][1:].lower()
        f.seek(0, 2)
        sz = f.tell()
        with open(os.path.join(tdir, 'size.txt'), 'wb') as s:
            s.write(str(sz).encode('ascii'))
        f.seek(0)
        mi = get_metadata(f, fmt)
    if mi.cover_data and mi.cover_data[1]:
        with open(os.path.join(tdir, 'cover.jpg'), 'wb') as f:
            f.write(mi.cover_data[1])
        mi.cover_data = (None, None)
        mi.cover = 'cover.jpg'
    opf = metadata_to_opf(mi, default_lang='und')
    with open(os.path.join(tdir, 'metadata.opf'), 'wb') as f:
        f.write(opf)

