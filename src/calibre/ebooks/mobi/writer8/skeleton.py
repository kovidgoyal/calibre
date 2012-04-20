#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re
from collections import namedtuple

from lxml import etree

from calibre.ebooks.oeb.base import XHTML_NS
from calibre.constants import ispy3

CHUNK_SIZE = 8192

# Tags to which kindlegen adds the aid attribute
aid_able_tags = {'a', 'abbr', 'address', 'article', 'aside', 'audio', 'b',
'bdo', 'blockquote', 'body', 'button', 'cite', 'code', 'dd', 'del', 'details',
'dfn', 'div', 'dl', 'dt', 'em', 'fieldset', 'figcaption', 'figure', 'footer',
'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'header', 'hgroup', 'i', 'ins', 'kbd',
'label', 'legend', 'li', 'map', 'mark', 'meter', 'nav', 'ol', 'output', 'p',
'pre', 'progress', 'q', 'rp', 'rt', 'samp', 'section', 'select', 'small',
'span', 'strong', 'sub', 'summary', 'sup', 'textarea', 'time', 'ul', 'var',
'video'}

_self_closing_pat = re.compile(bytes(
    r'<(?P<tag>%s)(?=[\s/])(?P<arg>[^>]*)/>'%('|'.join(aid_able_tags))),
    re.IGNORECASE)

def close_self_closing_tags(raw):
    return _self_closing_pat.sub(br'<\g<tag>\g<arg>></\g<tag>>', raw)

def path_to_node(node):
    ans = []
    parent = node.getparent()
    while parent is not None:
        ans.append(parent.index(node))
        node = parent
        parent = parent.getparent()
    return tuple(reversed(ans))

def node_from_path(root, path):
    parent = root
    for idx in path:
        parent = parent[idx]
    return parent

mychr = chr if ispy3 else unichr

def tostring(raw, **kwargs):
    ''' lxml *sometimes* represents non-ascii characters as hex entities in
    attribute values. I can't figure out exactly what circumstances cause it.
    It seems to happen when serializing a part of a larger tree. Since we need
    serialization to be the same when serializing full and partial trees, we
    manually replace all hex entities with their unicode codepoints. '''

    xml_declaration = kwargs.pop('xml_declaration', False)
    kwargs['encoding'] = unicode
    kwargs['xml_declaration'] = False
    ans = etree.tostring(raw, **kwargs)
    if xml_declaration:
        ans = '<?xml version="1.0" encoding="UTF-8"?>\n' + ans
    return re.sub(r'&#x([0-9A-Fa-f]+);', lambda m:mychr(int(m.group(1), 16)),
            ans)

class Chunk(object):

    def __init__(self, raw):
        self.raw = raw
        self.starts_tags = []
        self.ends_tags = []
        self.insert_pos = None

    def __len__(self):
        return len(self.raw)

    def merge(self, chunk):
        self.raw += chunk.raw
        self.ends_tags = chunk.ends_tags

    def __repr__(self):
        return 'Chunk(len=%r insert_pos=%r starts_tags=%r ends_tags=%r)'%(
                len(self.raw), self.insert_pos, self.starts_tags, self.ends_tags)

    __str__ = __repr__

class Skeleton(object):

    def __init__(self, file_number, item, root, chunks):
        self.file_number, self.item = file_number, item
        self.chunks = chunks

        self.skeleton = self.render(root)
        self.body_offset = self.skeleton.find('<body')
        self.calculate_metrics(root)

        self.calculate_insert_positions()

    def render(self, root):
        raw = tostring(root, xml_declaration=True)
        raw = raw.replace(b'<html', bytes('<html xmlns="%s"'%XHTML_NS), 1)
        return raw

    def calculate_metrics(self, root):
        Metric = namedtuple('Metric', 'start end')
        self.metrics = {}
        for tag in root.xpath('//*[@aid]'):
            text = (tag.text or '').encode('utf-8')
            raw = tostring(tag, with_tail=True)
            start_length = len(raw.partition(b'>')[0]) + len(text) + 1
            end_length = len(raw.rpartition(b'<')[-1]) + 1
            self.metrics[tag.get('aid')] = Metric(start_length, end_length)

    def calculate_insert_positions(self):
        pos = self.body_offset
        for chunk in self.chunks:
            for tag in chunk.starts_tags:
                pos += self.metrics[tag].start
            chunk.insert_pos = pos
            pos += len(chunk)
            for tag in chunk.ends_tags:
                pos += self.metrics[tag].end

    def rebuild(self):
        ans = self.skeleton
        for chunk in self.chunks:
            i = chunk.insert_pos
            ans = ans[:i] + chunk.raw + ans[i:]
        return ans

class Chunker(object):

    def __init__(self, oeb, data_func):
        self.oeb, self.log = oeb, oeb.log
        self.data = data_func

        self.skeletons = []

        # Set this to a list to enable dumping of the original and rebuilt
        # html files for debugging
        self.orig_dumps = []

        for i, item in enumerate(self.oeb.spine):
            root = self.remove_namespaces(self.data(item))
            body = root.xpath('//body')[0]
            body.tail = '\n'
            if self.orig_dumps is not None:
                self.orig_dumps.append(tostring(root, xml_declaration=True,
                    with_tail=True))
                self.orig_dumps[-1] = close_self_closing_tags(
                        self.orig_dumps[-1].replace(b'<html',
                        bytes('<html xmlns="%s"'%XHTML_NS), 1))

            # First pass: break up document into rendered strings of length no
            # more than CHUNK_SIZE
            chunks = []
            self.step_into_tag(body, chunks)

            # Second pass: Merge neighboring small chunks within the same
            # skeleton tag so as to have chunks as close to the CHUNK_SIZE as
            # possible.
            chunks = self.merge_small_chunks(chunks)

            # Third pass: Create the skeleton and calculate the insert position
            # for all chunks
            self.skeletons.append(Skeleton(i, item, root, chunks))

        if self.orig_dumps:
            self.dump()

    def remove_namespaces(self, root):
        lang = None
        for attr, val in root.attrib.iteritems():
            if attr.rpartition('}')[-1] == 'lang':
                lang = val

        # Remove all namespace information from the tree. This means namespaced
        # tags have their namespaces removed and all namespace declarations are
        # removed. We have to do this manual cloning of the tree as there is no
        # other way to remove namespace declarations in lxml. This is done so
        # that serialization creates clean HTML 5 markup with no namespaces. We
        # insert the XHTML namespace manually after serialization. The
        # preceding layers should have removed svg and any other non html
        # namespaced tags.
        attrib = {'lang':lang} if lang else {}
        nroot = etree.Element('html', attrib=attrib)
        nroot.text = root.text
        nroot.tail = '\n'

        for tag in root.iterdescendants(etree.Element):
            # We are ignoring all non tag entities in the tree
            # like comments and processing instructions, as they make the
            # chunking code even harder, for minimal gain.
            elem = nroot.makeelement(tag.tag.rpartition('}')[-1],
                    attrib={k.rpartition('}')[-1]:v for k, v in
                        tag.attrib.iteritems()})
            elem.text, elem.tail = tag.text, tag.tail
            parent = node_from_path(nroot, path_to_node(tag.getparent()))
            parent.append(elem)

        return nroot


    def step_into_tag(self, tag, chunks):
        aid = tag.get('aid')

        first_chunk_idx = len(chunks)

        # First handle any text
        if tag.text and tag.text.strip(): # Leave pure whitespace in the skel
            chunks.extend(self.chunk_up_text(tag.text))
            tag.text = None

        # Now loop over children
        for child in list(tag):
            raw = tostring(child, with_tail=False)
            raw = close_self_closing_tags(raw)
            if len(raw) > CHUNK_SIZE and child.get('aid', None):
                self.step_into_tag(child, chunks)
                if child.tail and child.tail.strip(): # Leave pure whitespace
                    chunks.extend(self.chunk_up_text(child.tail))
                    child.tail = None
            else:
                if len(raw) > CHUNK_SIZE:
                    self.log.warn('Tag %s has no aid and a too large chunk'
                            ' size. Adding anyway.'%child.tag)
                chunks.append(Chunk(raw))
                if child.tail:
                    chunks.extend(self.chunk_up_text(child.tail))
                tag.remove(child)

        if len(chunks) <= first_chunk_idx and chunks:
            raise ValueError('Stepped into a tag that generated no chunks.')

        # Mark the first and last chunks of this tag
        if chunks:
            chunks[first_chunk_idx].starts_tags.append(aid)
            chunks[-1].ends_tags.append(aid)

    def chunk_up_text(self, text):
        text = text.encode('utf-8')
        ans = []

        def split_multibyte_text(raw):
            if len(raw) <= CHUNK_SIZE:
                return raw, b''
            l = raw[:CHUNK_SIZE]
            l = l.decode('utf-8', 'ignore').encode('utf-8')
            return l, raw[len(l):]

        start, rest = split_multibyte_text(text)
        ans.append(start)
        while rest:
            start, rest = split_multibyte_text(rest)
            ans.append(b'<span class="AmznBigTextBlock">' + start + '</span>')
        return [Chunk(x) for x in ans]

    def merge_small_chunks(self, chunks):
        ans = chunks[:1]
        for chunk in chunks[1:]:
            prev = ans[-1]
            if (
                    chunk.starts_tags or # Starts a tag in the skel
                    len(chunk) + len(prev) > CHUNK_SIZE or # Too large
                    prev.ends_tags # Prev chunk ended a tag
                    ):
                ans.append(chunk)
            else:
                prev.merge(chunk)
        return ans

    def dump(self):
        import tempfile, shutil, os
        tdir = os.path.join(tempfile.gettempdir(), 'skeleton')
        self.log('Skeletons dumped to:', tdir)
        if os.path.exists(tdir):
            shutil.rmtree(tdir)
        orig = os.path.join(tdir, 'orig')
        rebuilt = os.path.join(tdir, 'rebuilt')
        for x in (orig, rebuilt):
            os.makedirs(x)
        for i, skeleton in enumerate(self.skeletons):
            with open(os.path.join(orig, '%04d.html'%i),  'wb') as f:
                f.write(self.orig_dumps[i])
            with open(os.path.join(rebuilt, '%04d.html'%i),  'wb') as f:
                f.write(skeleton.rebuild())

