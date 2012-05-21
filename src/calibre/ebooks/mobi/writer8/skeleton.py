#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re
from collections import namedtuple
from functools import partial

from lxml import etree

from calibre.ebooks.oeb.base import XHTML_NS, extract
from calibre.constants import ispy3
from calibre.ebooks.mobi.utils import to_base

CHUNK_SIZE = 8192

# References in links are stored with 10 digits
to_href = partial(to_base, base=32, min_num_digits=10)

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
    encoding = kwargs.pop('encoding', 'UTF-8')
    kwargs['encoding'] = unicode
    kwargs['xml_declaration'] = False
    ans = etree.tostring(raw, **kwargs)
    if xml_declaration:
        ans = '<?xml version="1.0" encoding="%s"?>\n'%encoding + ans
    return re.sub(r'&#x([0-9A-Fa-f]+);', lambda m:mychr(int(m.group(1), 16)),
            ans).encode(encoding)

class Chunk(object):

    def __init__(self, raw, parent_tag):
        self.raw = raw
        self.starts_tags = []
        self.ends_tags = []
        self.insert_pos = None
        self.parent_tag = parent_tag
        self.parent_is_body = False
        self.is_last_chunk = False
        self.is_first_chunk = False

    def __len__(self):
        return len(self.raw)

    def merge(self, chunk):
        self.raw += chunk.raw
        self.ends_tags = chunk.ends_tags

    def __repr__(self):
        return 'Chunk(len=%r insert_pos=%r starts_tags=%r ends_tags=%r)'%(
                len(self.raw), self.insert_pos, self.starts_tags, self.ends_tags)

    @property
    def selector(self):
        typ = 'S' if (self.is_last_chunk and not self.parent_is_body) else 'P'
        return "%s-//*[@aid='%s']"%(typ, self.parent_tag)

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

    def __len__(self):
        return len(self.skeleton) + sum([len(x.raw) for x in self.chunks])

    @property
    def raw_text(self):
        return b''.join([self.skeleton] + [x.raw for x in self.chunks])

class Chunker(object):

    def __init__(self, oeb, data_func, placeholder_map):
        self.oeb, self.log = oeb, oeb.log
        self.data = data_func
        self.placeholder_map = placeholder_map

        self.skeletons = []

        # Set this to a list to enable dumping of the original and rebuilt
        # html files for debugging
        orig_dumps = None

        for i, item in enumerate(self.oeb.spine):
            root = self.remove_namespaces(self.data(item))
            body = root.xpath('//body')[0]
            body.tail = '\n'

            if orig_dumps is not None:
                orig_dumps.append(tostring(root, xml_declaration=True,
                    with_tail=True))
                orig_dumps[-1] = close_self_closing_tags(
                        orig_dumps[-1].replace(b'<html',
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

        if orig_dumps:
            self.dump(orig_dumps)

        # Create the SKEL and Chunk tables
        self.skel_table = []
        self.chunk_table = []
        self.create_tables()

        # Set internal links
        text = b''.join(x.raw_text for x in self.skeletons)
        self.text = self.set_internal_links(text)

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

        # Remove Comments and ProcessingInstructions as kindlegen seems to
        # remove them as well
        for tag in root.iterdescendants():
            if tag.tag in {etree.Comment, etree.ProcessingInstruction}:
                extract(tag)

        for tag in root.iterdescendants():
            if tag.tag == etree.Entity:
                elem = etree.Entity(tag.name)
            else:
                tn = tag.tag
                if tn is not None:
                    tn = tn.rpartition('}')[-1]
                elem = nroot.makeelement(tn,
                        attrib={k.rpartition('}')[-1]:v for k, v in
                            tag.attrib.iteritems()})
                elem.text = tag.text
            elem.tail = tag.tail
            parent = node_from_path(nroot, path_to_node(tag.getparent()))
            parent.append(elem)

        return nroot

    def step_into_tag(self, tag, chunks):
        aid = tag.get('aid')
        is_body = tag.tag == 'body'

        first_chunk_idx = len(chunks)

        # First handle any text
        if tag.text and tag.text.strip(): # Leave pure whitespace in the skel
            chunks.extend(self.chunk_up_text(tag.text, aid))
            tag.text = None

        # Now loop over children
        for child in list(tag):
            raw = tostring(child, with_tail=False)
            if child.tag == etree.Entity:
                chunks.append(raw)
                if child.tail:
                    chunks.extend(self.chunk_up_text(child.tail, aid))
                continue
            raw = close_self_closing_tags(raw)
            if len(raw) > CHUNK_SIZE and child.get('aid', None):
                self.step_into_tag(child, chunks)
                if child.tail and child.tail.strip(): # Leave pure whitespace
                    chunks.extend(self.chunk_up_text(child.tail, aid))
                    child.tail = None
            else:
                if len(raw) > CHUNK_SIZE:
                    self.log.warn('Tag %s has no aid and a too large chunk'
                            ' size. Adding anyway.'%child.tag)
                chunks.append(Chunk(raw, aid))
                if child.tail:
                    chunks.extend(self.chunk_up_text(child.tail, aid))
                tag.remove(child)

        if len(chunks) <= first_chunk_idx and chunks:
            raise ValueError('Stepped into a tag that generated no chunks.')

        # Mark the first and last chunks of this tag
        if chunks:
            chunks[first_chunk_idx].starts_tags.append(aid)
            chunks[-1].ends_tags.append(aid)
            my_chunks = chunks[first_chunk_idx:]
            if my_chunks:
                my_chunks[0].is_first_chunk = True
                my_chunks[-1].is_last_chunk = True
                if is_body:
                    for chunk in my_chunks:
                        chunk.parent_is_body = True

    def chunk_up_text(self, text, parent_tag):
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
        return [Chunk(x, parent_tag) for x in ans]

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

    def create_tables(self):
        Skel = namedtuple('Skel',
                'file_number name chunk_count start_pos length')
        sp = 0
        for s in self.skeletons:
            s.start_pos = sp
            sp += len(s)
        self.skel_table = [Skel(s.file_number, 'SKEL%010d'%s.file_number,
            len(s.chunks), s.start_pos, len(s.skeleton)) for s in self.skeletons]

        Chunk = namedtuple('Chunk',
            'insert_pos selector file_number sequence_number start_pos length')
        num = 0
        for skel in self.skeletons:
            cp = 0
            for chunk in skel.chunks:
                self.chunk_table.append(
                    Chunk(chunk.insert_pos + skel.start_pos, chunk.selector,
                        skel.file_number, num, cp, len(chunk.raw)))
                cp += len(chunk.raw)
                num += 1

    def set_internal_links(self, text):
        ''' Update the internal link placeholders to point to the correct
        location, based on the chunk table.'''
        # A kindle:pos:fid link contains two base 32 numbers of the form
        # XXXX:YYYYYYYYYY
        # The first number is an index into the chunk table and the second is
        # an offset from the start of the chunk to the start of the tag pointed
        # to by the link.
        aid_map = {} # Map of aid to (pos, fid)
        for match in re.finditer(br'<[^>]+? aid=[\'"]([A-Z0-9]+)[\'"]', text):
            offset = match.start()
            pos_fid = None
            for chunk in self.chunk_table:
                if chunk.insert_pos <= offset < chunk.insert_pos + chunk.length:
                    pos_fid = (chunk.sequence_number, offset-chunk.insert_pos,
                            offset)
                    break
                if chunk.insert_pos > offset:
                    # This aid is in the skeleton, not in a chunk, so we use
                    # the chunk immediately after
                    pos_fid = (chunk.sequence_number, 0, offset)
                    break
            if pos_fid is None:
                raise ValueError('Could not find chunk for aid: %r'%
                        match.group(1))
            aid_map[match.group(1)] = pos_fid

        self.aid_offset_map = aid_map

        def to_placeholder(aid):
            pos, fid, _ = aid_map[aid]
            pos, fid = to_base(pos, min_num_digits=4), to_href(fid)
            return bytes(':off:'.join((pos, fid)))

        placeholder_map = {bytes(k):to_placeholder(v) for k, v in
                self.placeholder_map.iteritems()}

        # Now update the links
        def sub(match):
            raw = match.group()
            pl = match.group(1)
            try:
                return raw[:-19] + placeholder_map[pl]
            except KeyError:
                pass
            return raw

        return re.sub(br'<[^>]+(kindle:pos:fid:0000:off:[0-9A-Za-z]{10})', sub,
                text)

    def dump(self, orig_dumps):
        import tempfile, shutil, os
        tdir = os.path.join(tempfile.gettempdir(), 'skeleton')
        self.log('Skeletons dumped to:', tdir)
        if os.path.exists(tdir):
            shutil.rmtree(tdir)
        orig = os.path.join(tdir, 'orig')
        rebuilt = os.path.join(tdir, 'rebuilt')
        chunks = os.path.join(tdir, 'chunks')
        for x in (orig, rebuilt, chunks):
            os.makedirs(x)
        error = False
        for i, skeleton in enumerate(self.skeletons):
            for j, chunk in enumerate(skeleton.chunks):
                with open(os.path.join(chunks, 'file-%d-chunk-%d.html'%(i, j)),
                        'wb') as f:
                    f.write(chunk.raw)
            oraw, rraw = orig_dumps[i], skeleton.rebuild()
            with open(os.path.join(orig, '%04d.html'%i),  'wb') as f:
                f.write(oraw)
            with open(os.path.join(rebuilt, '%04d.html'%i),  'wb') as f:
                f.write(rraw)
            if oraw != rraw:
                error = True
        if error:
            raise ValueError('The before and after HTML differs. Run a diff '
                    'tool on the orig and rebuilt directories')
        else:
            self.log('Skeleton HTML before and after is identical.')


