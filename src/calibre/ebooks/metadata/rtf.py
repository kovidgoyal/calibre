#!/usr/bin/env python
# License: GPLv3 Copyright: 2008, Kovid Goyal <kovid at kovidgoyal.net>

"""
Edit metadata in RTF files.
"""

import codecs
import re

from calibre import force_unicode
from calibre.ebooks.metadata import MetaInformation
from polyglot.builtins import codepoint_to_chr, string_or_bytes, int_to_byte

title_pat    = re.compile(br'\{\\info.*?\{\\title(.*?)(?<!\\)\}', re.DOTALL)
author_pat   = re.compile(br'\{\\info.*?\{\\author(.*?)(?<!\\)\}', re.DOTALL)
comment_pat  = re.compile(br'\{\\info.*?\{\\subject(.*?)(?<!\\)\}', re.DOTALL)
tags_pat = re.compile(br'\{\\info.*?\{\\category(.*?)(?<!\\)\}', re.DOTALL)
publisher_pat = re.compile(br'\{\\info.*?\{\\manager(.*?)(?<!\\)\}', re.DOTALL)


def get_document_info(stream):
    """
    Extract the \\info block from an RTF file.
    Return the info block as a string and the position in the file at which it
    starts.
    @param stream: File like object pointing to the RTF file.
    """
    block_size = 4096
    stream.seek(0)
    found, block = False, b""
    while not found:
        prefix = block[-6:]
        block = prefix + stream.read(block_size)
        actual_block_size = len(block) - len(prefix)
        if len(block) == len(prefix):
            break
        idx = block.find(br'{\info')
        if idx >= 0:
            found = True
            pos = stream.tell() - actual_block_size + idx - len(prefix)
            stream.seek(pos)
        else:
            if block.find(br'\sect') > -1:
                break
    if not found:
        return None, 0
    data, count, = [], 0
    pos = stream.tell()
    while True:
        ch = stream.read(1)
        if ch == b'\\':
            data.append(ch + stream.read(1))
            continue
        if ch == b'{':
            count += 1
        elif ch == b'}':
            count -= 1
        data.append(ch)
        if count == 0:
            break
    return b''.join(data), pos


def detect_codepage(stream):
    pat = re.compile(br'\\ansicpg(\d+)')
    match = pat.search(stream.read(512))
    if match is not None:
        num = match.group(1)
        if num == b'0':
            num = b'1252'
        try:
            codec = (b'cp'+num).decode('ascii')
            codecs.lookup(codec)
            return codec
        except Exception:
            pass


def encode(unistr):
    if not isinstance(unistr, str):
        unistr = force_unicode(unistr)
    return ''.join(c if ord(c) < 128 else f'\\u{ord(c)}?' for c in unistr)


def decode(raw, codec):
    # https://en.wikipedia.org/wiki/Rich_Text_Format#Character_encoding

    def codepage(match):
        try:
            return int_to_byte(int(match.group(1), 16)).decode(codec)
        except ValueError:
            return '?'

    def uni(match):
        try:
            return codepoint_to_chr(int(match.group(1)))
        except Exception:
            return '?'

    if isinstance(raw, bytes):
        raw = raw.decode('ascii', 'replace')

    if codec is not None:
        raw = re.sub(r"\\'([a-fA-F0-9]{2})", codepage, raw)

    raw = re.sub(r'\\u([0-9]{3,5}).', uni, raw)
    return raw


def get_metadata(stream):
    """
    Return metadata as a L{MetaInfo} object
    """
    stream.seek(0)
    if stream.read(5) != br'{\rtf':
        return MetaInformation(_('Unknown'))
    block = get_document_info(stream)[0]
    if not block:
        return MetaInformation(_('Unknown'))

    stream.seek(0)
    cpg = detect_codepage(stream)
    stream.seek(0)

    title_match = title_pat.search(block)
    if title_match is not None:
        title = decode(title_match.group(1).strip(), cpg)
    else:
        title = _('Unknown')
    author_match = author_pat.search(block)
    if author_match is not None:
        author = decode(author_match.group(1).strip(), cpg)
    else:
        author = None
    mi = MetaInformation(title)
    if author:
        mi.authors = [x.strip() for x in author.split(',')]

    comment_match = comment_pat.search(block)
    if comment_match is not None:
        comment = decode(comment_match.group(1).strip(), cpg)
        mi.comments = comment
    tags_match = tags_pat.search(block)
    if tags_match is not None:
        tags = decode(tags_match.group(1).strip(), cpg)
        mi.tags = list(filter(None, (x.strip() for x in tags.split(','))))
    publisher_match = publisher_pat.search(block)
    if publisher_match is not None:
        publisher = decode(publisher_match.group(1).strip(), cpg)
        mi.publisher = publisher

    return mi


def create_metadata(stream, options):
    md = [r'{\info']
    if options.title:
        title = encode(options.title)
        md.append(r'{\title %s}'%(title,))
    if options.authors:
        au = options.authors
        if not isinstance(au, string_or_bytes):
            au = ', '.join(au)
        author = encode(au)
        md.append(r'{\author %s}'%(author,))
    comp = options.comment if hasattr(options, 'comment') else options.comments
    if comp:
        comment = encode(comp)
        md.append(r'{\subject %s}'%(comment,))
    if options.publisher:
        publisher = encode(options.publisher)
        md.append(r'{\manager %s}'%(publisher,))
    if options.tags:
        tags = ', '.join(options.tags)
        tags = encode(tags)
        md.append(r'{\category %s}'%(tags,))
    if len(md) > 1:
        md.append('}')
        stream.seek(0)
        src   = stream.read()
        ans = src[:6] + ''.join(md).encode('ascii') + src[6:]
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
    if src is None:
        create_metadata(stream, options)
    else:
        src = src.decode('ascii')
        olen = len(src)

        base_pat = r'\{\\name(.*?)(?<!\\)\}'

        def replace_or_create(src, name, val):
            val = encode(val)
            pat = re.compile(base_pat.replace('name', name), re.DOTALL)
            src, num = pat.subn(r'{\\' + name.replace('\\', r'\\') + ' ' + val.replace('\\', r'\\') + '}', src)
            if num == 0:
                src = add_metadata_item(src, name, val)
            return src

        if options.title is not None:
            src = replace_or_create(src, 'title', options.title)
        if options.comments is not None:
            src = replace_or_create(src, 'subject', options.comments)
        if options.authors is not None:
            src = replace_or_create(src, 'author', ', '.join(options.authors))
        if options.tags is not None:
            src = replace_or_create(src, 'category', ', '.join(options.tags))
        if options.publisher is not None:
            src = replace_or_create(src, 'manager', options.publisher)
        stream.seek(pos + olen)
        after = stream.read()
        stream.seek(pos)
        stream.truncate()
        stream.write(src.encode('ascii'))
        stream.write(after)


def find_tests():
    import unittest
    from io import BytesIO
    from calibre.ebooks.metadata.book.base import Metadata

    class Test(unittest.TestCase):

        def test_rtf_metadata(self):
            stream = BytesIO(br'{\rtf1\ansi\ansicpg1252}')
            m = Metadata('Test ø̄title', ['Author One', 'Author БTwo'])
            m.tags = 'tag1 見tag2'.split()
            m.comments = '<p>some ⊹comments</p>'
            m.publisher = 'publiSher'
            set_metadata(stream, m)
            stream.seek(0)
            o = get_metadata(stream)
            for attr in 'title authors publisher comments tags'.split():
                self.assertEqual(getattr(m, attr), getattr(o, attr))

    return unittest.defaultTestLoader.loadTestsFromTestCase(Test)
