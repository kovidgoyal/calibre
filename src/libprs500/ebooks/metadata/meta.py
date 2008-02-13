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
from libprs500.ebooks.metadata.rtf  import set_metadata as set_rtf_metadata
from libprs500.ebooks.lrf.meta      import set_metadata as set_lrf_metadata

from libprs500.ebooks.metadata import MetaInformation

def get_metadata(stream, stream_type='lrf'):
    if stream_type: stream_type = stream_type.lower()
    if stream_type in ('html', 'html', 'xhtml', 'xhtm'):
        stream_type = 'html'
    
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

_filename_pat = re.compile(r'(?P<title>.+) - (?P<author>[^_]+)')

def metadata_from_filename(name):
    name = os.path.splitext(name)[0]
    mi = MetaInformation(None, None)
    match = _filename_pat.search(name)
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
    if not mi.title:
        mi.title = name
    return mi
    