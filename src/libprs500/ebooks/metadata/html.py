#!/usr/bin/env  python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
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
    
    