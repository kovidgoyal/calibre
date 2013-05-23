#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import struct, re, os
from collections import namedtuple
from itertools import repeat, izip
from urlparse import urldefrag

from lxml import etree

from calibre.ebooks.mobi.reader.headers import NULL_INDEX
from calibre.ebooks.mobi.reader.index import read_index
from calibre.ebooks.mobi.reader.ncx import read_ncx, build_toc
from calibre.ebooks.mobi.reader.markup import expand_mobi8_markup
from calibre.ebooks.metadata.opf2 import Guide, OPFCreator
from calibre.ebooks.metadata.toc import TOC
from calibre.ebooks.mobi.utils import read_font_record
from calibre.ebooks.oeb.parse_utils import parse_html
from calibre.ebooks.oeb.base import XPath, XHTML, xml2text
from calibre.utils.imghdr import what

Part = namedtuple('Part',
    'num type filename start end aid')

Elem = namedtuple('Elem',
    'insert_pos toc_text file_number sequence_number start_pos '
    'length')

FlowInfo = namedtuple('FlowInfo',
        'type format dir fname')

# locate beginning and ending positions of tag with specific aid attribute
def locate_beg_end_of_tag(ml, aid):
    pattern = br'''<[^>]*\said\s*=\s*['"]%s['"][^>]*>''' % aid
    aid_pattern = re.compile(pattern, re.IGNORECASE)
    for m in re.finditer(aid_pattern, ml):
        plt = m.start()
        pgt = ml.find(b'>', plt+1)
        return plt, pgt
    return 0, 0

def reverse_tag_iter(block):
    ''' Iterate over all tags in block in reverse order, i.e. last tag
    to first tag. '''
    end = len(block)
    while True:
        pgt = block.rfind(b'>', 0, end)
        if pgt == -1:
            break
        plt = block.rfind(b'<', 0, pgt)
        if plt == -1:
            break
        yield block[plt:pgt+1]
        end = plt

class Mobi8Reader(object):

    def __init__(self, mobi6_reader, log):
        self.mobi6_reader, self.log = mobi6_reader, log
        self.header = mobi6_reader.book_header
        self.encrypted_fonts = []

    def __call__(self):
        self.mobi6_reader.check_for_drm()
        offset = 1
        res_end = len(self.mobi6_reader.sections)
        if self.mobi6_reader.kf8_type == 'joint':
            offset = self.mobi6_reader.kf8_boundary + 2
            res_end = self.mobi6_reader.kf8_boundary

        self.processed_records = self.mobi6_reader.extract_text(offset=offset)
        self.raw_ml = self.mobi6_reader.mobi_html
        with open('debug-raw.html', 'wb') as f:
            f.write(self.raw_ml)

        self.kf8_sections = self.mobi6_reader.sections[offset-1:]
        first_resource_index = self.header.first_image_index
        if first_resource_index in {-1, NULL_INDEX}:
            first_resource_index = self.header.records + 1
        self.resource_sections = \
                self.mobi6_reader.sections[first_resource_index:res_end]
        self.cover_offset = getattr(self.header.exth, 'cover_offset', None)

        self.read_indices()
        self.build_parts()
        guide = self.create_guide()
        ncx = self.create_ncx()
        resource_map = self.extract_resources()
        spine = self.expand_text(resource_map)
        return self.write_opf(guide, ncx, spine, resource_map)

    def read_indices(self):
        self.flow_table = ()

        if self.header.fdstidx != NULL_INDEX:
            header = self.kf8_sections[self.header.fdstidx][0]
            if header[:4] != b'FDST':
                raise ValueError('KF8 does not have a valid FDST record')
            sec_start, num_sections = struct.unpack_from(b'>LL', header, 4)
            secs = struct.unpack_from(b'>%dL' % (num_sections*2),
                    header, sec_start)
            self.flow_table = tuple(izip(secs[::2], secs[1::2]))

        self.files = []
        if self.header.skelidx != NULL_INDEX:
            table = read_index(self.kf8_sections, self.header.skelidx,
                    self.header.codec)[0]
            File = namedtuple('File',
                'file_number name divtbl_count start_position length')

            for i, text in enumerate(table.iterkeys()):
                tag_map = table[text]
                self.files.append(File(i, text, tag_map[1][0],
                    tag_map[6][0], tag_map[6][1]))

        self.elems = []
        if self.header.dividx != NULL_INDEX:
            table, cncx = read_index(self.kf8_sections, self.header.dividx,
                    self.header.codec)
            for i, text in enumerate(table.iterkeys()):
                tag_map = table[text]
                toc_text = cncx[tag_map[2][0]]
                self.elems.append(Elem(int(text), toc_text, tag_map[3][0],
                    tag_map[4][0], tag_map[6][0], tag_map[6][1]))

        self.guide = []
        if self.header.othidx != NULL_INDEX:
            table, cncx = read_index(self.kf8_sections, self.header.othidx,
                    self.header.codec)
            Item = namedtuple('Item',
                'type title pos_fid')

            for i, ref_type in enumerate(table.iterkeys()):
                tag_map = table[ref_type]
                 # ref_type, ref_title, div/frag number
                title = cncx[tag_map[1][0]]
                fileno = None
                if 3 in tag_map.keys():
                    fileno  = tag_map[3][0]
                if 6 in tag_map.keys():
                    fileno = tag_map[6]
                self.guide.append(Item(ref_type.decode(self.header.codec),
                    title, fileno))

    def build_parts(self):
        raw_ml = self.mobi6_reader.mobi_html
        self.flows = []
        self.flowinfo = []
        ft = self.flow_table if self.flow_table else [(0, len(raw_ml))]

        # now split the raw_ml into its flow pieces
        for start, end in ft:
            self.flows.append(raw_ml[start:end])

        # the first piece represents the xhtml text
        text = self.flows[0]
        self.flows[0] = b''

        # walk the <skeleton> and <div> tables to build original source xhtml
        # files *without* destroying any file position information needed for
        # later href processing and create final list of file separation start:
        # stop points and etc in partinfo
        self.parts = []
        self.partinfo = []
        divptr = 0
        baseptr = 0
        for skelnum, skelname, divcnt, skelpos, skellen in self.files:
            baseptr = skelpos + skellen
            skeleton = text[skelpos:baseptr]
            inspos_warned = False
            for i in xrange(divcnt):
                insertpos, idtext, filenum, seqnum, startpos, length = \
                                    self.elems[divptr]
                if i == 0:
                    aidtext = idtext[12:-2]
                    filename = 'part%04d.html' % filenum
                part = text[baseptr:baseptr + length]
                insertpos = insertpos - skelpos
                head = skeleton[:insertpos]
                tail = skeleton[insertpos:]
                if (tail.find(b'>') < tail.find(b'<') or head.rfind(b'>') <
                    head.rfind(b'<')):
                    # There is an incomplete tag in either the head or tail.
                    # This can happen for some badly formed KF8 files, see for
                    # example, https://bugs.launchpad.net/bugs/1082669
                    if not inspos_warned:
                        self.log.warn(
                            'The div table for %s has incorrect insert '
                                'positions. Calculating manually.'%skelname)
                        inspos_warned = True
                    bp, ep = locate_beg_end_of_tag(skeleton, aidtext if
                        isinstance(aidtext, bytes) else aidtext.encode('utf-8'))
                    if bp != ep:
                        insertpos = ep + 1 + startpos

                skeleton = skeleton[0:insertpos] + part + skeleton[insertpos:]
                baseptr = baseptr + length
                divptr += 1
            self.parts.append(skeleton)
            self.partinfo.append(Part(skelnum, 'text', filename, skelpos,
                baseptr, aidtext))

        # The primary css style sheet is typically stored next followed by any
        # snippets of code that were previously inlined in the
        # original xhtml but have been stripped out and placed here.
        # This can include local CDATA snippets and and svg sections.

        # The problem is that for most browsers and ereaders, you can not
        # use <img src="imageXXXX.svg" /> to import any svg image that itself
        # properly uses an <image/> tag to import some raster image - it
        # should work according to the spec but does not for almost all browsers
        # and ereaders and causes epub validation issues because those  raster
        # images are in manifest but not in xhtml text - since they only
        # referenced from an svg image

        # So we need to check the remaining flow pieces to see if they are css
        # or svg images.  if svg images, we must check if they have an <image/>
        # and if so inline them into the xhtml text pieces.

        # there may be other sorts of pieces stored here but until we see one
        # in the wild to reverse engineer we won't be able to tell

        self.flowinfo.append(FlowInfo(None, None, None, None))
        svg_tag_pattern = re.compile(br'''(<svg[^>]*>)''', re.IGNORECASE)
        image_tag_pattern = re.compile(br'''(<(?:svg:)?image[^>]*>)''', re.IGNORECASE)
        for j in xrange(1, len(self.flows)):
            flowpart = self.flows[j]
            nstr = '%04d' % j
            m = svg_tag_pattern.search(flowpart)
            if m is not None:
                # svg
                typ = 'svg'
                start = m.start()
                m2 = image_tag_pattern.search(flowpart)
                if m2 is not None:
                    format = 'inline'
                    dir = None
                    fname = None
                    # strip off anything before <svg if inlining
                    flowpart = re.sub(br'(</?)svg:', r'\1', flowpart[start:])
                else:
                    format = 'file'
                    dir = "images"
                    fname = 'svgimg' + nstr + '.svg'
            else:
                # search for CDATA and if exists inline it
                if flowpart.find(b'[CDATA[') >= 0:
                    typ = 'css'
                    flowpart = b'<style type="text/css">\n' + flowpart + b'\n</style>\n'
                    format = 'inline'
                    dir = None
                    fname = None
                else:
                    # css - assume as standalone css file
                    typ = 'css'
                    format = 'file'
                    dir = "styles"
                    fname = nstr + '.css'

            self.flows[j] = flowpart
            self.flowinfo.append(FlowInfo(typ, format, dir, fname))

    def get_file_info(self, pos):
        ''' Get information about the part (file) that exists at pos in
        the raw markup '''
        for part in self.partinfo:
            if pos >= part.start and pos < part.end:
                return part
        return Part(*repeat(None, len(Part._fields)))

    def get_id_tag_by_pos_fid(self, posfid, offset):
        # first convert kindle:pos:fid and offset info to position in file
        insertpos, idtext, filenum, seqnm, startpos, length = self.elems[posfid]
        pos = insertpos + offset
        fi = self.get_file_info(pos)
        # an existing "id=" must exist in original xhtml otherwise it would not
        # have worked for linking.  Amazon seems to have added its own
        # additional "aid=" inside tags whose contents seem to represent some
        # position information encoded into Base32 name.

        # so find the closest "id=" before position the file by actually
        # searching in that file
        idtext = self.get_id_tag(pos)
        return '%s/%s'%(fi.type, fi.filename), idtext

    def get_id_tag(self, pos):
        # Find the first tag with a named anchor (name or id attribute) before
        # pos
        fi = self.get_file_info(pos)
        if fi.num is None and fi.start is None:
            raise ValueError('No file contains pos: %d'%pos)
        textblock = self.parts[fi.num]
        npos = pos - fi.start
        pgt = textblock.find(b'>', npos)
        plt = textblock.find(b'<', npos)
        # if npos inside a tag then search all text before the its end of tag marker
        # else not in a tag need to search the preceding tag
        if plt == npos or pgt < plt:
            npos = pgt + 1
        textblock = textblock[0:npos]
        id_re = re.compile(br'''<[^>]+\sid\s*=\s*['"]([^'"]+)['"]''')
        name_re = re.compile(br'''<\s*a\s*\sname\s*=\s*['"]([^'"]+)['"]''')
        for tag in reverse_tag_iter(textblock):
            m = id_re.match(tag) or name_re.match(tag)
            if m is not None:
                return m.group(1)

        # No tag found, link to start of file
        return b''

    def create_guide(self):
        guide = Guide()
        has_start = False
        for ref_type, ref_title, pos_fid in self.guide:
            try:
                if len(pos_fid) != 2:
                    continue
            except TypeError:
                continue  # thumbnailstandard record, ignore it
            linktgt, idtext = self.get_id_tag_by_pos_fid(*pos_fid)
            if idtext:
                linktgt += b'#' + idtext
            g = Guide.Reference(linktgt, os.getcwdu())
            g.title, g.type = ref_title, ref_type
            if g.title == 'start' or g.type == 'text':
                has_start = True
            guide.append(g)

        so = self.header.exth.start_offset
        if so not in {None, NULL_INDEX} and not has_start:
            fi = self.get_file_info(so)
            if fi.filename is not None:
                idtext = self.get_id_tag(so).decode(self.header.codec)
                linktgt = fi.filename
                if idtext:
                    linktgt += '#' + idtext
                g = Guide.Reference('%s/%s'%(fi.type, linktgt), os.getcwdu())
                g.title, g.type = 'start', 'text'
                guide.append(g)

        return guide

    def create_ncx(self):
        index_entries = read_ncx(self.kf8_sections, self.header.ncxidx,
                self.header.codec)
        remove = []

        # Add href and anchor info to the index entries
        for entry in index_entries:
            pos_fid = entry['pos_fid']
            if pos_fid is None:
                pos = entry['pos']
                fi = self.get_file_info(pos)
                if fi.filename is None:
                    raise ValueError('Index entry has invalid pos: %d'%pos)
                idtag = self.get_id_tag(pos).decode(self.header.codec)
                href = '%s/%s'%(fi.type, fi.filename)
            else:
                try:
                    href, idtag = self.get_id_tag_by_pos_fid(*pos_fid)
                except ValueError:
                    self.log.warn('Invalid entry in NCX (title: %s), ignoring'
                                  %entry['text'])
                    remove.append(entry)
                    continue

            entry['href'] = href
            entry['idtag'] = idtag

        for e in remove:
            index_entries.remove(e)

        # Build the TOC object
        return build_toc(index_entries)

    def extract_resources(self):
        resource_map = []
        for x in ('fonts', 'images'):
            os.mkdir(x)

        for i, sec in enumerate(self.resource_sections):
            fname_idx = i+1
            data = sec[0]
            typ = data[:4]
            href = None
            if typ in {b'FLIS', b'FCIS', b'SRCS', b'\xe9\x8e\r\n',
                    b'RESC', b'BOUN', b'FDST', b'DATP', b'AUDI', b'VIDE'}:
                pass  # Ignore these records
            elif typ == b'FONT':
                font = read_font_record(data)
                href = "fonts/%05d.%s" % (fname_idx, font['ext'])
                if font['err']:
                    self.log.warn('Reading font record %d failed: %s'%(
                        fname_idx, font['err']))
                    if font['headers']:
                        self.log.debug('Font record headers: %s'%font['headers'])
                with open(href.replace('/', os.sep), 'wb') as f:
                    f.write(font['font_data'] if font['font_data'] else
                            font['raw_data'])
                if font['encrypted']:
                    self.encrypted_fonts.append(href)
            else:
                imgtype = what(None, data)
                if imgtype is None:
                    from calibre.utils.magick.draw import identify_data
                    try:
                        imgtype = identify_data(data)[2]
                    except Exception:
                        imgtype = 'unknown'
                href = 'images/%05d.%s'%(fname_idx, imgtype)
                with open(href.replace('/', os.sep), 'wb') as f:
                    f.write(data)

            resource_map.append(href)

        return resource_map

    def expand_text(self, resource_map):
        return expand_mobi8_markup(self, resource_map, self.log)

    def write_opf(self, guide, toc, spine, resource_map):
        mi = self.header.exth.mi
        if (self.cover_offset is not None and self.cover_offset <
                len(resource_map)):
            mi.cover = resource_map[self.cover_offset]

        if len(list(toc)) < 2:
            self.log.warn('KF8 has no metadata Table of Contents')

            for ref in guide:
                if ref.type == 'toc':
                    href = ref.href()
                    href, frag = urldefrag(href)
                    if os.path.exists(href.replace('/', os.sep)):
                        try:
                            toc = self.read_inline_toc(href, frag)
                        except:
                            self.log.exception('Failed to read inline ToC')

        opf = OPFCreator(os.getcwdu(), mi)
        opf.guide = guide

        def exclude(path):
            return os.path.basename(path) == 'debug-raw.html'

        opf.create_manifest_from_files_in([os.getcwdu()], exclude=exclude)
        opf.create_spine(spine)
        opf.set_toc(toc)

        with open('metadata.opf', 'wb') as of, open('toc.ncx', 'wb') as ncx:
            opf.render(of, ncx, 'toc.ncx')
        return 'metadata.opf'

    def read_inline_toc(self, href, frag):
        ans = TOC()
        base_href = '/'.join(href.split('/')[:-1])
        with open(href.replace('/', os.sep), 'rb') as f:
            raw = f.read().decode(self.header.codec)
        root = parse_html(raw, log=self.log)
        body = XPath('//h:body')(root)
        reached = False
        if body:
            start = body[0]
        else:
            start = None
            reached = True
        if frag:
            elems = XPath('//*[@id="%s"]'%frag)(root)
            if elems:
                start = elems[0]

        def node_depth(elem):
            ans = 0
            parent = elem.getparent()
            while parent is not None:
                parent = parent.getparent()
                ans += 1
            return ans

        # Layer the ToC based on nesting order in the source HTML
        current_depth = None
        parent = ans
        seen = set()
        links = []
        for elem in root.iterdescendants(etree.Element):
            if reached and elem.tag == XHTML('a') and elem.get('href',
                    False):
                href = elem.get('href')
                href, frag = urldefrag(href)
                href = base_href + '/' + href
                text = xml2text(elem).strip()
                if (text, href, frag) in seen:
                    continue
                seen.add((text, href, frag))
                links.append((text, href, frag, node_depth(elem)))
            elif elem is start:
                reached = True

        depths = sorted(set(x[-1] for x in links))
        depth_map = {x:i for i, x in enumerate(depths)}
        for text, href, frag, depth in links:
            depth = depth_map[depth]
            if current_depth is None:
                current_depth = 0
                parent.add_item(href, frag, text)
            elif current_depth == depth:
                parent.add_item(href, frag, text)
            elif current_depth < depth:
                parent = parent[-1] if len(parent) > 0 else parent
                parent.add_item(href, frag, text)
                current_depth += 1
            else:
                delta = current_depth - depth
                while delta > 0 and parent.parent is not None:
                    parent = parent.parent
                    delta -= 1
                parent.add_item(href, frag, text)
                current_depth = depth
        return ans

