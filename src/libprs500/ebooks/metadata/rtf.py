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
"""
Edit metadata in RTF files.
"""
import re, cStringIO, sys

from libprs500.ebooks.metadata import MetaInformation, get_parser

title_pat    = re.compile(r'\{\\info.*?\{\\title(.*?)(?<!\\)\}', re.DOTALL)
author_pat   = re.compile(r'\{\\info.*?\{\\author(.*?)(?<!\\)\}', re.DOTALL)
comment_pat  = re.compile(r'\{\\info.*?\{\\subject(.*?)(?<!\\)\}', re.DOTALL)
category_pat = re.compile(r'\{\\info.*?\{\\category(.*?)(?<!\\)\}', re.DOTALL)

def get_document_info(stream):
    """ 
    Extract the \info block from an RTF file.
    Return the info block as a string and the position in the file at which it
    starts.
    @param stream: File like object pointing to the RTF file.
    """
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
            if block.find(r'\sect') > -1:
                break
    if not found:
        return None, 0
    data, count, = cStringIO.StringIO(), 0
    pos = stream.tell()
    while True:
        ch = stream.read(1)
        if ch == '\\':
            data.write(ch + stream.read(1))
            continue
        if ch == '{':
            count += 1
        elif ch == '}':
            count -= 1
        data.write(ch)
        if count == 0:
            break
    return data.getvalue(), pos

def get_metadata(stream):
    """ Return metadata as a L{MetaInfo} object """
    stream.seek(0)
    if stream.read(5) != r'{\rtf':
        name = stream.name if hasattr(stream, 'name') else repr(stream)
        raise Exception('Not a valid RTF file: '+name)
    block = get_document_info(stream)[0]
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
        comment = comment_match.group(1).strip()
    category_match = category_pat.search(block)
    if category_match:
        category = category_match.group(1).strip()
    mi = MetaInformation(title, author)
    if author:
        au = author.split(',')
        mi.authors = []
        for i in au:
            mi.authors.extend(i.split('&'))
    mi.comments = comment
    mi.category = category
    return mi
    

def create_metadata(stream, options):
    md = r'{\info'
    if options.title:
        title = options.title.encode('ascii', 'ignore')
        md += r'{\title %s}'%(title,)
    if options.authors:
        au = options.authors
        if not isinstance(au, basestring):
            au = u', '.join(au)
        author = au.encode('ascii', 'ignore')
        md += r'{\author %s}'%(author,)
    if options.category:
        category = options.category.encode('ascii', 'ignore')
        md += r'{\category %s}'%(category,)
    comp = options.comment if hasattr(options, 'comment') else options.comments
    if comp:
        comment = comp.encode('ascii', 'ignore')
        md += r'{\subject %s}'%(comment,)
    if len(md) > 6:
        md += '}'
        stream.seek(0)
        src   = stream.read()
        ans = src[:6] + md + src[6:]
        stream.seek(0)
        stream.write(ans)

def set_metadata(stream, options):
    '''
    Modify/add RTF metadata in stream
    @param options: Object with metadata attributes title, author, comment, category
    '''
    def add_metadata_item(src, name, val):
        index = src.rindex('}')
        return src[:index] + r'{\ '[:-1] + name + ' ' + val + '}}'
    src, pos = get_document_info(stream)
    if not src:
        create_metadata(stream, options)
    else:
        olen = len(src)
         
        base_pat = r'\{\\name(.*?)(?<!\\)\}'
        title = options.title
        if title != None:
            title = title.encode('ascii', 'replace')
            pat = re.compile(base_pat.replace('name', 'title'), re.DOTALL)        
            if pat.search(src):
                src = pat.sub(r'{\\title ' + title + r'}', src)
            else:
                src = add_metadata_item(src, 'title', title)
        comment = options.comments
        if comment != None:
            comment = comment.encode('ascii', 'replace')
            pat = re.compile(base_pat.replace('name', 'subject'), re.DOTALL)
            if pat.search(src):
                src = pat.sub(r'{\\subject ' + comment + r'}', src)
            else:
                src = add_metadata_item(src, 'subject', comment)
        author = options.authors
        if author != None:
            author =  ', '.join(author)
            author = author.encode('ascii', 'ignore')
            pat = re.compile(base_pat.replace('name', 'author'), re.DOTALL)        
            if pat.search(src):
                src = pat.sub(r'{\\author ' + author + r'}', src)
            else:
                src = add_metadata_item(src, 'author', author)
        category = options.category
        if category != None:
            category = category.encode('ascii', 'replace')
            pat = re.compile(base_pat.replace('name', 'category'), re.DOTALL)        
            if pat.search(src):
                src = pat.sub(r'{\\category ' + category + r'}', src)
            else:
                src = add_metadata_item(src, 'category', category)
        stream.seek(pos + olen)
        after = stream.read()
        stream.seek(pos)
        stream.truncate()
        stream.write(src)
        stream.write(after)
    
def option_parser():
    return get_parser('rtf')

def main(args=sys.argv):
    parser = option_parser()
    options, args = parser.parse_args(args)
    if len(args) != 2:
        parser.print_help()
        sys.exit(1)
    stream = open(args[1], 'r+b')
    if options.authors:
        options.authors = options.authors.split(',')
    options.comments = options.comment 
    set_metadata(stream, options)
    mi = get_metadata(stream)
    return mi

if __name__ == '__main__':
    main()