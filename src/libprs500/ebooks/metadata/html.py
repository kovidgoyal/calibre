#!/usr/bin/env  python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

##    Copyright (C) 2008 Kovid Goyal kovid@kovidgoyal.net
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
'''
Try to read metadata from an HTML file.
'''

import re

from libprs500.ebooks.metadata import MetaInformation

def get_metadata(stream):
    src = stream.read()
    
    # Title
    title = None
    pat = re.compile(r'<!--.*?TITLE=[\'"]([^"\']+)[\'"].*?-->', re.DOTALL)
    match = pat.search(src)
    if match:
        title = match.group(1)
    else:
        pat = re.compile('<title>([^<>]+?)</title>', re.IGNORECASE)
        match = pat.search(src)
        if match:
            title = match.group(1)
        
    # Author
    author = None
    pat = re.compile(r'<!--.*?AUTHOR=[\'"]([^"\']+)[\'"].*?-->', re.DOTALL)
    match = pat.search(src)
    if match:
        author = match.group(1).replace(',', ';')
        
    mi = MetaInformation(title, [author] if author else None)
    
    # Publisher
    pat = re.compile(r'<!--.*?PUBLISHER=[\'"]([^"\']+)[\'"].*?-->', re.DOTALL)
    match = pat.search(src)
    if match:
        mi.publisher = match.group(1)
        
    # ISBN
    pat = re.compile(r'<!--.*?ISBN=[\'"]([^"\']+)[\'"].*?-->', re.DOTALL)
    match = pat.search(src)
    if match:
        isbn = match.group(1)
        mi.isbn = re.sub(r'[^0-9xX]', '', isbn)
        
    return mi
    
    