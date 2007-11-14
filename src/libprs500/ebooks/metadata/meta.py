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

from libprs500.ebooks.metadata.rtf import get_metadata as rtf_metadata
from libprs500.ebooks.lrf.meta     import get_metadata as lrf_metadata
from libprs500.ebooks.metadata.pdf import get_metadata as pdf_metadata
from libprs500.ebooks.metadata.lit import get_metadata as lit_metadata
from libprs500.ebooks.metadata.rtf import set_metadata as set_rtf_metadata
from libprs500.ebooks.lrf.meta     import set_metadata as set_lrf_metadata

from libprs500.ebooks.metadata import MetaInformation

def get_metadata(stream, stream_type='lrf'):
    if stream_type: stream_type = stream_type.lower()
    if stream_type == 'rtf':
        return rtf_metadata(stream)
    if stream_type == 'lrf':
        return lrf_metadata(stream)
    if stream_type == 'pdf':
        return pdf_metadata(stream)
    if stream_type == 'lit':
        return lit_metadata(stream)
    return MetaInformation(None, None)

def set_metadata(stream, mi, stream_type='lrf'):
    if stream_type: stream_type = stream_type.lower()
    if stream_type == 'lrf':
        set_lrf_metadata(stream, mi)
    elif stream_type == 'rtf':
        set_rtf_metadata(stream, mi)
    
