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
    title, author, comment, category = None, None, None, None
    stream.seek(0)
    if stream.read(5) != r'{\rtf':
        return MetaInformation(None, None)
    block = get_document_info(stream)[0]
    if not block:
        return MetaInformation(None, None)

    stream.seek(0)
    cpg = detect_codepage(stream)
    stream.seek(0)

    title_match = title_pat.search(block)
    if title_match:
        title = decode(title_match.group(1).strip(), cpg)
    author_match = author_pat.search(block)
    if author_match:
        author = decode(author_match.group(1).strip(), cpg)
    comment_match = comment_pat.search(block)
    if comment_match:
        comment = decode(comment_match.group(1).strip(), cpg)
    category_match = category_pat.search(block)
    if category_match:
        category = decode(category_match.group(1).strip(), cpg)
    mi = MetaInformation(title, author)
    if author:
        mi.authors = string_to_authors(author)
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
    if options.get('category', None):
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
        category = options.get('category', None)
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

