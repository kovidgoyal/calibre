__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import os, re, collections

from calibre.ebooks.metadata.rtf  import get_metadata as rtf_metadata
from calibre.ebooks.metadata.fb2  import get_metadata as fb2_metadata
from calibre.ebooks.lrf.meta      import get_metadata as lrf_metadata
from calibre.ebooks.metadata.pdf  import get_metadata as pdf_metadata
from calibre.ebooks.metadata.lit  import get_metadata as lit_metadata
from calibre.ebooks.metadata.epub import get_metadata as epub_metadata
from calibre.ebooks.metadata.html import get_metadata as html_metadata
from calibre.ebooks.mobi.reader   import get_metadata as mobi_metadata
from calibre.ebooks.metadata.opf  import OPFReader 
from calibre.ebooks.metadata.rtf  import set_metadata as set_rtf_metadata
from calibre.ebooks.lrf.meta      import set_metadata as set_lrf_metadata

from calibre.ebooks.metadata import MetaInformation

_METADATA_PRIORITIES = [
                       'html', 'htm', 'xhtml', 'xhtm',
                       'rtf', 'fb2', 'pdf', 'prc',
                       'epub', 'lit', 'lrf', 'mobi',
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
        mi.smart_update(get_metadata(stream, stream_type=ext, use_libprs_metadata=True))
        if getattr(mi, 'application_id', None) is not None:
            return mi
    
    return mi

def get_metadata(stream, stream_type='lrf', use_libprs_metadata=False):
    if stream_type: stream_type = stream_type.lower()
    if stream_type in ('html', 'html', 'xhtml', 'xhtm'):
        stream_type = 'html'
    if stream_type in ('mobi', 'prc'):
        stream_type = 'mobi'
        
    opf = None
    if hasattr(stream, 'name'):
        c = os.path.splitext(stream.name)[0]+'.opf'
        if os.access(c, os.R_OK):
            opf = opf_metadata(os.path.abspath(c))
        
    if use_libprs_metadata and getattr(opf, 'application_id', None) is not None:
        return opf
    
    try:
        func = eval(stream_type + '_metadata')
        mi = func(stream)
    except NameError:
        mi = MetaInformation(None, None)
        
    name = os.path.basename(getattr(stream, 'name', ''))
    base = metadata_from_filename(name)
    if not base.authors:
        base.authors = ['Unknown']
    if not base.title:
        base.title = 'Unknown'
    base.smart_update(mi)
    if opf is not None:
        base.update(opf)
        
    return base

def set_metadata(stream, mi, stream_type='lrf'):
    if stream_type: stream_type = stream_type.lower()
    if stream_type == 'lrf':
        set_lrf_metadata(stream, mi)
    elif stream_type == 'rtf':
        set_rtf_metadata(stream, mi)

_filename_pat = re.compile(ur'(?P<title>.+) - (?P<author>[^_]+)')

def get_filename_pat():
    return _filename_pat.pattern

def set_filename_pat(pat):
    global _filename_pat
    _filename_pat = re.compile(pat)

def metadata_from_filename(name, pat=None):
    name = os.path.splitext(name)[0]
    mi = MetaInformation(None, None)
    if pat is None:
        pat = _filename_pat
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
        except IndexError, ValueError:
            pass
    if not mi.title:
        mi.title = name
    return mi

def opf_metadata(opfpath):
    if hasattr(opfpath, 'read'):
        f = opfpath
        opfpath = getattr(f, 'name', '')
    else:
        f = open(opfpath, 'rb')
    try:
        opf = OPFReader(f, os.path.dirname(opfpath))
        if opf.application_id is not None:
            mi = MetaInformation(opf, None)
            if hasattr(opf, 'cover') and opf.cover:
                cpath = os.path.join(os.path.dirname(opfpath), opf.cover)
                if os.access(cpath, os.R_OK):                     
                    fmt = cpath.rpartition('.')[-1]
                    data = open(cpath, 'rb').read()
                    mi.cover_data = (fmt, data)
            return mi
    except:
        pass
