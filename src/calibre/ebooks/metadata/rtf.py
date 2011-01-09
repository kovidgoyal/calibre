__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
"""
Edit metadata in RTF files.
"""
import re, cStringIO, codecs

from calibre.ebooks.metadata import MetaInformation, string_to_authors

title_pat    = re.compile(r'\{\\info.*?\{\\title(.*?)(?<!\\)\}', re.DOTALL)
author_pat   = re.compile(r'\{\\info.*?\{\\author(.*?)(?<!\\)\}', re.DOTALL)
comment_pat  = re.compile(r'\{\\info.*?\{\\subject(.*?)(?<!\\)\}', re.DOTALL)
tags_pat = re.compile(r'\{\\info.*?\{\\keywords(.*?)(?<!\\)\}', re.DOTALL)
publisher_pat = re.compile(r'\{\\info.*?\{\\manager(.*?)(?<!\\)\}', re.DOTALL)

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
        actual_block_size = len(block) - len(prefix)
        if len(block) == len(prefix):
            break
        idx = block.find(r'{\info')
        if idx >= 0:
            found = True
            pos = stream.tell() - actual_block_size + idx - len(prefix)
            stream.seek(pos)
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

def detect_codepage(stream):
    pat = re.compile(r'\\ansicpg(\d+)')
    match = pat.search(stream.read(512))
    if match is not None:
        num = match.group(1)
        if num == '0':
            num = '1250'
        codec = 'cp'+num
        try:
            codecs.lookup(codec)
            return codec
        except:
            pass

def decode(raw, codec):
    if codec is not None:
        def codepage(match):
            return chr(int(match.group(1), 16))
        raw = re.sub(r"\\'([a-fA-F0-9]{2})", codepage, raw)
        raw = raw.decode(codec)

    def uni(match):
        return unichr(int(match.group(1)))
    raw = re.sub(r'\\u([0-9]{4}).', uni, raw)
    return raw

def get_metadata(stream):
    """ Return metadata as a L{MetaInfo} object """
    stream.seek(0)
    if stream.read(5) != r'{\rtf':
        return MetaInformation(_('Unknown'), None)
    block = get_document_info(stream)[0]
    if not block:
        return MetaInformation(_('Unknown'), None)

    stream.seek(0)
    cpg = detect_codepage(stream)
    stream.seek(0)
    
    title_match = title_pat.search(block)
    if title_match:
        title = decode(title_match.group(1).strip(), cpg)
    else:
        title = _('Unknown')
    author_match = author_pat.search(block)
    if author_match:
        author = decode(author_match.group(1).strip(), cpg)
    else:
        author = None
    mi = MetaInformation(title, author)
    if author:
        mi.authors = string_to_authors(author)
    
    comment_match = comment_pat.search(block)
    if comment_match:
        comment = decode(comment_match.group(1).strip(), cpg)
        mi.comments = comment
    tags_match = tags_pat.search(block)
    if tags_match:
        tags = decode(tags_match.group(1).strip(), cpg)
        mi.tags = tags
    publisher_match = publisher_pat.search(block)
    if publisher_match:
        publisher = decode(publisher_match.group(1).strip(), cpg)
        mi.publisher = publisher
    
    return mi

def create_metadata(stream, options):
    md = [r'{\info']
    if options.title:
        title = options.title.encode('ascii', 'ignore')
        md.append(r'{\title %s}'%(title,))
    if options.authors:
        au = options.authors
        if not isinstance(au, basestring):
            au = u', '.join(au)
        author = au.encode('ascii', 'ignore')
        md.append(r'{\author %s}'%(author,))
    comp = options.comment if hasattr(options, 'comment') else options.comments
    if comp:
        comment = comp.encode('ascii', 'ignore')
        md.append(r'{\subject %s}'%(comment,))
    if options.publisher:
        publisher = options.publisher.encode('ascii', 'ignore')
        md.append(r'{\manager %s}'%(publisher,))
    if options.tags:
        tags = u', '.join(options.tags)
        tags = tags.encode('ascii', 'ignore')
        md.append(r'{\keywords %s}'%(tags,))
    if len(md) > 1:
        md.append('}')
        stream.seek(0)
        src   = stream.read()
        ans = src[:6] + ''.join(md) + src[6:]
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
    print 'I was thre'
    if src is not None:
        create_metadata(stream, options)
    else:
        olen = len(src)

        base_pat = r'\{\\name(.*?)(?<!\\)\}'
        title = options.title
        if title is not None:
            title = title.encode('ascii', 'replace')
            pat = re.compile(base_pat.replace('name', 'title'), re.DOTALL)
            if pat.search(src):
                src = pat.sub(r'{\\title ' + title + r'}', src)
            else:
                src = add_metadata_item(src, 'title', title)
        comment = options.comments
        if comment is not None:
            comment = comment.encode('ascii', 'replace')
            pat = re.compile(base_pat.replace('name', 'subject'), re.DOTALL)
            if pat.search(src):
                src = pat.sub(r'{\\subject ' + comment + r'}', src)
            else:
                src = add_metadata_item(src, 'subject', comment)
        author = options.authors
        if author is not None:
            author =  ', '.join(author)
            author = author.encode('ascii', 'ignore')
            pat = re.compile(base_pat.replace('name', 'author'), re.DOTALL)
            if pat.search(src):
                src = pat.sub(r'{\\author ' + author + r'}', src)
            else:
                src = add_metadata_item(src, 'author', author)
        tags = options.tags
        if tags is not None:
            tags =  ', '.join(tags)
            tags = tags.encode('ascii', 'ignore')
            pat = re.compile(base_pat.replace('name', 'keywords'), re.DOTALL)
            if pat.search(src):
                src = pat.sub(r'{\\keywords ' + tags + r'}', src)
            else:
                src = add_metadata_item(src, 'keywords', tags)
        publisher = options.publisher
        if publisher is not None:
            publisher = publisher.encode('ascii', 'replace')
            pat = re.compile(base_pat.replace('name', 'manager'), re.DOTALL)
            if pat.search(src):
                src = pat.sub(r'{\\manager ' + publisher + r'}', src)
            else:
                src = add_metadata_item(src, 'manager', publisher)
        stream.seek(pos + olen)
        after = stream.read()
        stream.seek(pos)
        stream.truncate()
        stream.write(src)
        stream.write(after)

