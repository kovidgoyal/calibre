##    Copyright (C) 2006 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import os, re

from libprs500.ebooks.metadata.rtf  import get_metadata as rtf_metadata
from libprs500.ebooks.lrf.meta      import get_metadata as lrf_metadata
from libprs500.ebooks.metadata.pdf  import get_metadata as pdf_metadata
from libprs500.ebooks.metadata.lit  import get_metadata as lit_metadata
from libprs500.ebooks.metadata.epub import get_metadata as epub_metadata
from libprs500.ebooks.metadata.html import get_metadata as html_metadata
from libprs500.ebooks.mobi.reader   import get_metadata as mobi_metadata
from libprs500.ebooks.metadata.opf  import OPFReader 
from libprs500.ebooks.metadata.rtf  import set_metadata as set_rtf_metadata
from libprs500.ebooks.lrf.meta      import set_metadata as set_lrf_metadata

from libprs500.ebooks.metadata import MetaInformation

def get_metadata(stream, stream_type='lrf', use_libprs_metadata=False):
    if stream_type: stream_type = stream_type.lower()
    if stream_type in ('html', 'html', 'xhtml', 'xhtm'):
        stream_type = 'html'
    if stream_type in ('mobi', 'prc'):
        stream_type = 'mobi'
    if use_libprs_metadata and hasattr(stream, 'name'):
        mi = libprs_metadata(stream.name)
        if mi is not None:
            return mi
    try:
        func = eval(stream_type + '_metadata')
        mi = func(stream)
    except NameError:
        mi = MetaInformation(None, None)
        
    name = os.path.basename(stream.name) if hasattr(stream, 'name') else ''
    base = metadata_from_filename(name)
    if not base.authors:
        base.authors = ['Unknown']
    base.smart_update(mi)
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
    
def libprs_metadata(name):
    if os.path.basename(name) != 'metadata.opf':
        name = os.path.join(os.path.dirname(name), 'metadata.opf')
    if os.access(name, os.R_OK):
        print name
        name = os.path.abspath(name)
        f = open(name, 'rb')
        opf = OPFReader(f, os.path.dirname(name))
        try:
            if opf.libprs_id is not None:
                return MetaInformation(opf, None)
        except:
            pass