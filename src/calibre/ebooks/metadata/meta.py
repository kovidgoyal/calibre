from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import os, re, collections

from calibre.utils.config import prefs
 
from calibre.ebooks.metadata.opf2 import OPF

from calibre.customize.ui import get_file_type_metadata, set_file_type_metadata
from calibre.ebooks.metadata import MetaInformation

_METADATA_PRIORITIES = [
                       'html', 'htm', 'xhtml', 'xhtm',
                       'rtf', 'fb2', 'pdf', 'prc', 'odt',
                       'epub', 'lit', 'lrx', 'lrf', 'mobi',
                       'rb', 'imp'
                      ]

# The priorities for loading metadata from different file types
# Higher values should be used to update metadata from lower values
METADATA_PRIORITIES = collections.defaultdict(lambda:0)
for i, ext in enumerate(_METADATA_PRIORITIES):
    METADATA_PRIORITIES[ext] = i

def path_to_ext(path):
    return os.path.splitext(path)[1][1:].lower()

def metadata_from_formats(formats):
    mi = MetaInformation(None, None)
    formats.sort(cmp=lambda x,y: cmp(METADATA_PRIORITIES[path_to_ext(x)],
                                     METADATA_PRIORITIES[path_to_ext(y)]))
    for path in formats:
        ext = path_to_ext(path)
        stream = open(path, 'rb')
        try:
            mi.smart_update(get_metadata(stream, stream_type=ext, use_libprs_metadata=True))
        except:
            continue
        if getattr(mi, 'application_id', None) is not None:
            return mi
    
    if not mi.title:
        mi.title = _('Unknown')
    if not mi.authors:
        mi.authors = [_('Unknown')]

    return mi

def get_metadata(stream, stream_type='lrf', use_libprs_metadata=False):
    if stream_type: stream_type = stream_type.lower()
    if stream_type in ('html', 'html', 'xhtml', 'xhtm', 'xml'):
        stream_type = 'html'
    if stream_type in ('mobi', 'prc'):
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
    if prefs['read_file_metadata']:
        mi = get_file_type_metadata(stream, stream_type)
        
    name = os.path.basename(getattr(stream, 'name', ''))
    base = metadata_from_filename(name)
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
    name = os.path.splitext(name)[0]
    mi = MetaInformation(None, None)
    if pat is None:
        pat = re.compile(prefs.get('filename_pattern'))
    match = pat.search(name)
    if match:
        try:
            mi.title = match.group('title')
        except IndexError:
            pass
        try:
            mi.authors = [match.group('author')]
        except IndexError:
            pass
        try:
            au = match.group('authors')
            aus = au.split(',')
            authors = []
            for a in aus:
                authors.extend(a.split('&'))
            mi.authors = authors
        except IndexError:
            pass
        try:
            mi.series = match.group('series')
        except IndexError:
            pass
        try:
            si = match.group('series_index')
            mi.series_index = int(si)
        except (IndexError, ValueError, TypeError):
            pass
        try:
            si = match.group('isbn')
            mi.isbn = si
        except (IndexError, ValueError):
            pass
    if not mi.title:
        mi.title = name
    return mi

def opf_metadata(opfpath):
    if hasattr(opfpath, 'read'):
        f = opfpath
        opfpath = getattr(f, 'name', os.getcwd())
    else:
        f = open(opfpath, 'rb')
    try:
        opf = OPF(f, os.path.dirname(opfpath))
        if opf.application_id is not None:
            mi = MetaInformation(opf)
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
