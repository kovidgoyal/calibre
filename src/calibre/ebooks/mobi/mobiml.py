'''
Transform XHTML/OPS-ish content into Mobipocket HTML 3.2.
'''
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.cam>'

import sys
import os
import copy
import re
from lxml import etree
from calibre.ebooks.oeb.base import namespace, barename
from calibre.ebooks.oeb.base import XHTML, XHTML_NS
from calibre.ebooks.oeb.stylizer import Stylizer
from calibre.ebooks.oeb.transforms.flatcss import KeyMapper

MBP_NS = 'http://mobipocket.com/ns/mbp'
def MBP(name): return '{%s}%s' % (MBP_NS, name)

HEADER_TAGS = set(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
NESTABLE_TAGS = set(['ol', 'ul', 'li', 'table', 'tr', 'td'])
SPECIAL_TAGS = set(['hr', 'br'])
CONTENT_TAGS = set(['img', 'hr', 'br'])

PAGE_BREAKS = set(['always', 'odd', 'even'])

COLLAPSE = re.compile(r'[ \t\r\n\v]+')

class BlockState(object):
    def __init__(self, body):
        self.body = body
        self.nested = []
        self.para = None
        self.inline = None
        self.vpadding = 0.
        self.vmargin = 0.
        self.left = 0.
        self.pbreak = False
        self.istate = None

class FormatState(object):
    def __init__(self):
        self.halign = 'auto'
        self.indent = 0.
        self.fsize = 3
        self.ids = set()
        self.valign = 'baseline'
        self.italic = False
        self.bold = False
        self.preserve = True
        self.href = None
        self.attrib = {}

    def __eq__(self, other):
        return self.fsize == other.fsize \
               and self.italic == other.italic \
               and self.bold == other.bold \
               and self.href == other.href \
               and self.valign == other.valign

    def __ne__(self, other):
        return not self.__eq__(other)


class MobiMLizer(object):
    def __init__(self):
        pass

    def transform(self, oeb, context):
        self.oeb = oeb
        self.profile = profile = context.dest
        self.fnums = fnums = dict((v, k) for k, v in profile.fnums.items())
        self.fmap = KeyMapper(profile.fbase, profile.fbase, fnums.keys())
        self.mobimlize_spine()

    def mobimlize_spine(self):
        for item in self.oeb.spine:
            stylizer = Stylizer(item.data, item.href, self.oeb, self.profile)
            data = item.data
            data.remove(data.find(XHTML('head')))
            body = data.find(XHTML('body'))
            nbody = etree.Element(XHTML('body'))
            self.mobimlize_elem(body, stylizer, BlockState(nbody),
                                [FormatState()])
            data.replace(body, nbody)

    def mobimlize_font(self, ptsize):
        return self.fnums[self.fmap[ptsize]]

    def mobimlize_measure(self, ptsize):
        if isinstance(ptsize, basestring):
            return ptsize
        # All MobiML measures occur in the default font-space
        fbase = self.profile.fbase
        if ptsize < fbase:
            return "%dpt" % int(round(ptsize * 2))
        return "%dem" % int(round(ptsize / fbase))

    def mobimlize_content(self, tag, text, bstate, istates):
        istate = istates[-1]
        if istate.ids:
            body = bstate.body
            index = max((0, len(body) - 2))
            for id in istate.ids:
                body.insert(index, etree.Element('a', attrib={'id': id}))
            istate.ids.clear()
        para = bstate.para
        if tag in SPECIAL_TAGS and not text:
            para = para if para is not None else bstate.body
        elif para is None:
            bstate.istate = None
            if bstate.pbreak:
                etree.SubElement(bstate.body, MBP('pagebreak'))
                bstate.pbreak = False
            if tag in NESTABLE_TAGS:
                parent = bstate.nested[-1] if bstate.nested else bstate.body
                para = wrapper = etree.SubElement(parent, tag)
                bstate.nested.append(para)
            elif bstate.left > 0 and istate.indent >= 0:
                para = wrapper = etree.SubElement(bstate.body, 'blockquote')
                left = int(round(bstate.left / self.profile.fbase)) - 1
                while left > 0:
                    para = etree.SubElement(para, 'blockquote')
                    left -= 1
            else:
                ptag = tag if tag in HEADER_TAGS else 'p'
                para = wrapper = etree.SubElement(bstate.body, ptag)
            bstate.inline = bstate.para = para
            vspace = bstate.vpadding + bstate.vmargin
            bstate.vpadding = bstate.vmargin = 0
            wrapper.attrib['height'] = self.mobimlize_measure(vspace)
            para.attrib['width'] = self.mobimlize_measure(istate.indent)
            if istate.halign != 'auto':
                wrapper.attrib['align'] = istate.halign
        pstate = bstate.istate
        if tag in CONTENT_TAGS:
            bstate.inline = para
            pstate = bstate.istate = None
            etree.SubElement(para, tag, attrib=istate.attrib)
        if not text:
            return
        if not pstate or istate != pstate:
            inline = para
            valign = istate.valign
            fsize = istate.fsize
            href = istate.href
            if valign == 'super':
                inline = etree.SubElement(inline, 'sup')
            elif valign == 'sub':
                inline = etree.SubElement(inline, 'sub')
            if fsize != 3:
                inline = etree.SubElement(inline, 'font', size=str(fsize))
            if istate.italic:
                inline = etree.SubElement(inline, 'i')
            if istate.bold:
                inline = etree.SubElement(inline, 'b')
            if href:
                inline = etree.SubElement(inline, 'a', href=href)
            bstate.inline = inline
        bstate.istate = istate
        inline = bstate.inline
        if inline == para:
            if len(para) == 0:
                para.text = (para.text or '') + text
            else:
                last = para[-1]
                last.tail = (last.tail or '') + text
        else:
            inline.text = (inline.text or '') + text
    
    def mobimlize_elem(self, elem, stylizer, bstate, istates):
        if not isinstance(elem.tag, basestring) \
           or namespace(elem.tag) != XHTML_NS:
            return
        istate = copy.copy(istates[-1])
        istates.append(istate)
        tag = barename(elem.tag)
        style = stylizer.style(elem)
        left = 0
        isblock = style['display'] not in ('inline', 'inline-block')
        isblock = isblock and tag != 'br'
        if isblock:
            bstate.para = None
            margin = style['margin-left']
            if not isinstance(margin, (int, float)):
                margin = 0
            padding = style['padding-left']
            if not isinstance(padding, (int, float)):
                padding = 0
            left = margin + padding
            bstate.left += left
            bstate.vmargin = max((bstate.vmargin, style['margin-top']))
            padding = style['padding-top']
            if isinstance(padding, (int, float)) and padding > 0:
                bstate.vpadding += bstate.vmargin
                bstate.vpadding = padding
        if style['page-break-before'] in PAGE_BREAKS:
            bstate.pbreak = True
        istate.fsize = self.mobimlize_font(style['font-size'])
        istate.italic = True if style['font-style'] == 'italic' else False
        weight = style['font-weight']
        if isinstance(weight, (int, float)):
            istate.bold = True if weight > 400 else False
        else:
            istate.bold = True if weight in ('bold', 'bolder') else False
        istate.indent = style['text-indent']
        istate.halign = style['text-align']
        istate.preserve = (style['white-space'] in ('pre', 'pre-wrap'))
        valign = style['vertical-align']
        if valign in ('super', 'sup') \
           or (isinstance(valign, (int, float)) and valign > 0):
            istate.valign = 'super'
        elif valign == 'sub' \
           or (isinstance(valign, (int, float)) and valign < 0):
            istate.valign = 'sub'
        else:
            istate.valign = 'baseline'
        if 'id' in elem.attrib:
            istate.ids.add(elem.attrib['id'])
        if 'name' in elem.attrib:
            istate.ids.add(elem.attrib['name'])
        if tag == 'a' and 'href' in elem.attrib:
            istate.href = elem.attrib['href']
        istate.attrib.clear()
        if tag == 'img' and 'src' in elem.attrib:
            istate.attrib['src'] = elem.attrib['src']
            istate.attrib['align'] = 'baseline'
        if tag == 'hr' and 'width' in style.cssdict():
            istate.attrib['width'] = mobimlize_measure(style['width'])
        text = None
        if elem.text:
            if istate.preserve:
                text = elem.text
            elif len(elem) > 0 and elem.text.isspace():
                text = None
            else:
                text = COLLAPSE.sub(' ', elem.text)
        if text or tag in CONTENT_TAGS:
            self.mobimlize_content(tag, text, bstate, istates)
        for child in elem:
            self.mobimlize_elem(child, stylizer, bstate, istates)
            tail = None
            if child.tail:
                if istate.preserve:
                    tail = child.tail
                elif bstate.para is None and child.tail.isspace():
                    tail = None
                else:
                    tail = COLLAPSE.sub(' ', child.tail)
            if tail:
                self.mobimlize_content(tag, tail, bstate, istates)
        if style['page-break-after'] in PAGE_BREAKS:
            bstate.pbreak = True
        if isblock:
            para = bstate.para
            if para is not None and para.text == u'\xa0':
                para.getparent().replace(para, etree.Element('br'))
            bstate.para = None
            bstate.left -= left
            bstate.vmargin = max((bstate.vmargin, style['margin-bottom']))
            padding = style['padding-bottom']
            if isinstance(padding, (int, float)) and padding > 0:
                bstate.vpadding += bstate.vmargin
                bstate.vpadding = padding
        if bstate.nested:
            bstate.nested.pop()
        istates.pop()
