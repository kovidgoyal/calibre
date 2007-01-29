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

import re, cStringIO

from libprs500.metadata import MetaInformation

title_pat = re.compile(r'\{\\info.*?\{\\title(.*?)\}', re.DOTALL)
author_pat = re.compile(r'\{\\info.*?\{\\author(.*?)\}', re.DOTALL)
comment_pat = re.compile(r'\{\\info.*?\{\\subject(.*?)\}', re.DOTALL)
category_pat = re.compile(r'\{\\info.*?\{\\category(.*?)\}', re.DOTALL)

def get_document_info(stream):
    block_size = 4096
    stream.seek(0)
    found, block = False, ""
    while not found:
        prefix = block[-6:] 
        block = prefix + stream.read(block_size)
        if len(block) == len(prefix):
            break
        idx = block.find(r'{\info')
        if idx >= 0:
            found = True
            stream.seek(stream.tell() - block_size + idx - len(prefix))
        else:
            stream.seek(stream.tell())
    if not found:
        return None, 0
    data, count, = cStringIO.StringIO(), 0
    pos = stream.tell()
    while True:
        ch = stream.read(1)
        if ch == '{':
            count += 1
        elif ch == '}':
            count -= 1
        data.write(ch)
        if count == 0:
            break
    return data.getvalue(), pos

def get_metadata(stream):
    stream.seek(0)
    if stream.read(5) != r'{\rtf':
        raise Exception('Not a valid RTF file')
    block, pos = get_document_info(stream)
    if not block:
        return MetaInformation(None, None)
    title, author, comment, category = None, None, None, None
    title_match = title_pat.search(block)
    if title_match:
        title = title_match.group(1).strip()
    author_match = author_pat.search(block)
    if author_match:
        author = author_match.group(1).strip()
    comment_match = comment_pat.search(block)
    if comment_match:
        title = comment_match.group(1).strip()
    category_match = category_pat.search(block)
    if category_match:
        category = category_match.group(1).strip()
    mi = MetaInformation(title, author)
    mi.comments = comment
    mi.category = category
    return mi
    
def main():
    import sys
    print get_metadata(open(sys.argv[1]))

if __name__ == '__main__':
    main()