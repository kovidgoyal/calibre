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
NESTABLE_TAGS = set(['ol', 'ul', 'li', 'table', 'tr', 'td', 'th'])
TABLE_TAGS = set(['table', 'tr', 'td', 'th'])
SPECIAL_TAGS = set(['hr', 'br'])
CONTENT_TAGS = set(['img', 'hr', 'br'])

PAGE_BREAKS = set(['always', 'odd', 'even'])

COLLAPSE = re.compile(r'[ \t\r\n\v]+')

def asfloat(value):
    if not isinstance(value, (int, long, float)):
        return 0.0
    return float(value)

class BlockState(object):
    def __init__(self, body):
        self.body = body
        self.nested = []
        self.para = None
        self.inline = None
        self.vpadding = 0.
        self.vmargin = 0.
        self.pbreak = False
        self.istate = None
        self.content = False

class FormatState(object):
    def __init__(self):
        self.left = 0.
        self.halign = 'auto'
        self.indent = 0.
        self.fsize = 3
        self.ids = set()
        self.valign = 'baseline'
        self.italic = False
        self.bold = False
        self.preserve = False
        self.family = 'serif'
        self.href = None
        self.list_num = 0
        self.attrib = {}

    def __eq__(self, other):
        return self.fsize == other.fsize \
               and self.italic == other.italic \
               and self.bold == other.bold \
               and self.href == other.href \
               and self.valign == other.valign \
               and self.preserve == other.preserve \
               and self.family == other.family

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
        fbase = self.profile.fbase
        if ptsize < fbase:
            return "%dpt" % int(round(ptsize))
        return "%dem" % int(round(ptsize / fbase))

    def preize_text(self, text):
        text = unicode(text).replace(u' ', u'\xa0')
        text = text.replace('\r\n', '\n')
        text = text.replace('\r', '\n')
        lines = text.split('\n')
        result = lines[:1]
        for line in lines[1:]:
            result.append(etree.Element('br'))
            if line:
                result.append(line)
        return result
    
    def mobimlize_content(self, tag, text, bstate, istates):
        bstate.content = True
        istate = istates[-1]
        para = bstate.para
        if tag in SPECIAL_TAGS and not text:
            para = para if para is not None else bstate.body
        elif para is None:
            body = bstate.body
            if bstate.pbreak:
                etree.SubElement(body, MBP('pagebreak'))
                bstate.pbreak = False
            if istate.ids:
                for id in istate.ids:
                    etree.SubElement(body, 'a', attrib={'id': id})
                istate.ids.clear()
            bstate.istate = None
            parent = bstate.nested[-1] if bstate.nested else bstate.body
            indent = istate.indent
            left = istate.left
            if indent < 0 and abs(indent) < left:
                left += indent
                indent = 0
            elif indent != 0 and abs(indent) < self.profile.fbase:
                indent = (indent / abs(indent)) * self.profile.fbase
            if tag in NESTABLE_TAGS:
                para = wrapper = etree.SubElement(parent, tag)
                bstate.nested.append(para)
                if tag == 'li' and len(istates) > 1:
                    istates[-2].list_num += 1
                    para.attrib['value'] = str(istates[-2].list_num)
            elif left > 0 and indent >= 0:
                para = wrapper = etree.SubElement(parent, 'blockquote')
                para = wrapper
                emleft = int(round(left / self.profile.fbase)) - 1
                emleft = min((emleft, 10))
                while emleft > 0:
                    para = etree.SubElement(para, 'blockquote')
                    emleft -= 1
            else:
                ptag = tag if tag in HEADER_TAGS else 'p'
                para = wrapper = etree.SubElement(parent, ptag)
            bstate.inline = bstate.para = para
            vspace = bstate.vpadding + bstate.vmargin
            bstate.vpadding = bstate.vmargin = 0
            if tag not in TABLE_TAGS:
                wrapper.attrib['height'] = self.mobimlize_measure(vspace)
                para.attrib['width'] = self.mobimlize_measure(indent)
            elif tag == 'table' and vspace > 0:
                body = bstate.body
                vspace = int(round(vspace / self.profile.fbase))
                index = max((0, len(body) - 1))
                while vspace > 0:
                    body.insert(index, etree.Element('br'))
                    vspace -= 1
            if istate.halign != 'auto':
                para.attrib['align'] = istate.halign
        pstate = bstate.istate
        if tag in CONTENT_TAGS:
            bstate.inline = para
            pstate = bstate.istate = None
            etree.SubElement(para, tag, attrib=istate.attrib)
        elif tag in TABLE_TAGS:
            para.attrib['valign'] = 'top'
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
            if istate.family == 'monospace':
                inline = etree.SubElement(inline, 'tt')
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
        content = self.preize_text(text) if istate.preserve else [text]
        for item in content:
            if isinstance(item, basestring):
                if len(inline) == 0:
                    inline.text = (inline.text or '') + item
                else:
                    last = inline[-1]
                    last.tail = (last.tail or '') + item
            else:
                inline.append(item)
    
    def mobimlize_elem(self, elem, stylizer, bstate, istates):
        if not isinstance(elem.tag, basestring) \
           or namespace(elem.tag) != XHTML_NS:
            return
        style = stylizer.style(elem)
        if style['display'] == 'none' \
           or style['visibility'] == 'hidden':
            return
        tag = barename(elem.tag)
        istate = copy.copy(istates[-1])
        istate.list_num = 0
        istates.append(istate)
        left = 0
        display = style['display']
        isblock = not display.startswith('inline')
        isblock = isblock and style['float'] == 'none'
        isblock = isblock and tag != 'br'
        if isblock:
            bstate.para = None
            istate.halign = style['text-align']
            istate.indent = style['text-indent']
            if style['margin-left'] == 'auto' \
               and style['margin-right'] == 'auto':
                istate.halign = 'center'
            margin = asfloat(style['margin-left'])
            padding = asfloat(style['padding-left'])
            if tag != 'body':
                left = margin + padding
            istate.left += left
            vmargin = asfloat(style['margin-top'])
            bstate.vmargin = max((bstate.vmargin, vmargin))
            vpadding = asfloat(style['padding-top'])
            if vpadding > 0:
                bstate.vpadding += bstate.vmargin
                bstate.vmargin = 0
                bstate.vpadding += vpadding
        else:
            margin = asfloat(style['margin-left'])
            padding = asfloat(style['padding-left'])
            lspace = margin + padding
            if lspace > 0:
                spaces = int(round((lspace * 3) / style['font-size']))
                elem.text = (u'\xa0' * spaces) + (elem.text or '')
            margin = asfloat(style['margin-right'])
            padding = asfloat(style['padding-right'])
            rspace = margin + padding
            if rspace > 0:
                spaces = int(round((rspace * 3) / style['font-size']))
                if len(elem) == 0:
                    elem.text = (elem.text or '') + (u'\xa0' * spaces)
                else:
                    last = elem[-1]
                    last.text = (last.text or '') + (u'\xa0' * spaces)
        if bstate.content and style['page-break-before'] in PAGE_BREAKS:
            bstate.pbreak = True
        istate.fsize = self.mobimlize_font(style['font-size'])
        istate.italic = True if style['font-style'] == 'italic' else False
        weight = style['font-weight']
        istate.bold = weight in ('bold', 'bolder') or asfloat(weight) > 400
        istate.preserve = (style['white-space'] in ('pre', 'pre-wrap'))
        if 'monospace' in style['font-family']:
            istate.family = 'monospace'
        elif 'sans-serif' in style['font-family']:
            istate.family = 'sans-serif'
        else:
            istate.family = 'serif'
        valign = style['vertical-align']
        if valign in ('super', 'sup') or asfloat(valign) > 0:
            istate.valign = 'super'
        elif valign == 'sub'  or asfloat(valign) < 0:
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
            for prop in ('width', 'height'):
                if style[prop] != 'auto':
                    value = style[prop]
                    if value == getattr(self.profile, prop):
                        result = '100%'
                    else:
                        ems = int(round(value / self.profile.fbase))
                        result = "%dem" % ems
                    istate.attrib[prop] = result
        elif tag == 'hr' and asfloat(style['width']) > 0:
            prop = style['width'] / self.profile.width
            istate.attrib['width'] = "%d%%" % int(round(prop * 100))
        elif display == 'table':
            tag = 'table'
        elif display == 'table-row':
            tag = 'tr'
        elif display == 'table-cell':
            tag = 'td'
        text = None
        if elem.text:
            if istate.preserve:
                text = elem.text
            elif len(elem) > 0 and elem.text.isspace():
                text = None
            else:
                text = COLLAPSE.sub(' ', elem.text)
        if text or tag in CONTENT_TAGS or tag in NESTABLE_TAGS:
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
        if bstate.content and style['page-break-after'] in PAGE_BREAKS:
            bstate.pbreak = True
        if isblock:
            para = bstate.para
            if para is not None and para.text == u'\xa0':
                para.getparent().replace(para, etree.Element('br'))
            bstate.para = None
            bstate.istate = None
            vmargin = asfloat(style['margin-bottom'])
            bstate.vmargin = max((bstate.vmargin, vmargin))
            vpadding = asfloat(style['padding-bottom'])
            if vpadding > 0:
                bstate.vpadding += bstate.vmargin
                bstate.vmargin = 0
                bstate.vpadding += vpadding
        if tag in NESTABLE_TAGS and bstate.nested:
            bstate.nested.pop()
        istates.pop()
