'''
Transform XHTML/OPS-ish content into Mobipocket HTML 3.2.
'''
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.cam>'

import copy
import re
from lxml import etree
from calibre.ebooks.oeb.base import namespace, barename
from calibre.ebooks.oeb.base import XHTML, XHTML_NS, OEB_DOCS
from calibre.ebooks.oeb.stylizer import Stylizer
from calibre.ebooks.oeb.transforms.flatcss import KeyMapper

MBP_NS = 'http://mobipocket.com/ns/mbp'
def MBP(name): return '{%s}%s' % (MBP_NS, name)

MOBI_NSMAP = {None: XHTML_NS, 'mbp': MBP_NS}

HEADER_TAGS = set(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
# GR: Added 'caption' to both sets
NESTABLE_TAGS = set(['ol', 'ul', 'li', 'table', 'tr', 'td', 'th', 'caption'])
TABLE_TAGS = set(['table', 'tr', 'td', 'th', 'caption'])

SPECIAL_TAGS = set(['hr', 'br'])
CONTENT_TAGS = set(['img', 'hr', 'br'])

NOT_VTAGS = HEADER_TAGS | NESTABLE_TAGS | TABLE_TAGS | SPECIAL_TAGS | \
    CONTENT_TAGS
PAGE_BREAKS = set(['always', 'left', 'right'])

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
        self.anchor = None
        self.vpadding = 0.
        self.vmargin = 0.
        self.pbreak = False
        self.istate = None
        self.content = False

class FormatState(object):
    def __init__(self):
        self.rendered = False
        self.left = 0.
        self.halign = 'auto'
        self.indent = 0.
        self.fsize = 3
        self.ids = set()
        self.italic = False
        self.bold = False
        self.strikethrough = False
        self.underline = False
        self.preserve = False
        self.family = 'serif'
        self.bgcolor = 'transparent'
        self.fgcolor = 'black'
        self.href = None
        self.list_num = 0
        self.attrib = {}

    def __eq__(self, other):
        return self.fsize == other.fsize \
               and self.italic == other.italic \
               and self.bold == other.bold \
               and self.href == other.href \
               and self.preserve == other.preserve \
               and self.family == other.family \
               and self.bgcolor == other.bgcolor \
               and self.fgcolor == other.fgcolor \
               and self.strikethrough == other.strikethrough \
               and self.underline == other.underline

    def __ne__(self, other):
        return not self.__eq__(other)


class MobiMLizer(object):
    def __init__(self, ignore_tables=False):
        self.ignore_tables = ignore_tables

    def __call__(self, oeb, context):
        oeb.logger.info('Converting XHTML to Mobipocket markup...')
        self.oeb = oeb
        self.opts = context
        self.profile = profile = context.dest
        self.fnums = fnums = dict((v, k) for k, v in profile.fnums.items())
        self.fmap = KeyMapper(profile.fbase, profile.fbase, fnums.keys())
        self.remove_html_cover()
        self.mobimlize_spine()

    def remove_html_cover(self):
        oeb = self.oeb
        if not oeb.metadata.cover \
           or 'cover' not in oeb.guide:
            return
        href = oeb.guide['cover'].href
        del oeb.guide['cover']
        item = oeb.manifest.hrefs[href]
        if item.spine_position is not None:
            oeb.spine.remove(item)
            if item.media_type in OEB_DOCS:
                self.oeb.manifest.remove(item)

    def mobimlize_spine(self):
        'Iterate over the spine and convert it to MOBIML'
        for item in self.oeb.spine:
            stylizer = Stylizer(item.data, item.href, self.oeb, self.opts, self.profile)
            body = item.data.find(XHTML('body'))
            nroot = etree.Element(XHTML('html'), nsmap=MOBI_NSMAP)
            nbody = etree.SubElement(nroot, XHTML('body'))
            self.mobimlize_elem(body, stylizer, BlockState(nbody),
                                [FormatState()])
            item.data = nroot

    def mobimlize_font(self, ptsize):
        return self.fnums[self.fmap[ptsize]]

    def mobimlize_measure(self, ptsize):
        if isinstance(ptsize, basestring):
            return ptsize
        embase = self.profile.fbase
        if round(ptsize) < embase:
            return "%dpt" % int(round(ptsize))
        return "%dem" % int(round(ptsize / embase))

    def preize_text(self, text):
        text = unicode(text).replace(u' ', u'\xa0')
        text = text.replace('\r\n', '\n')
        text = text.replace('\r', '\n')
        lines = text.split('\n')
        result = lines[:1]
        for line in lines[1:]:
            result.append(etree.Element(XHTML('br')))
            if line:
                result.append(line)
        return result

    def mobimlize_content(self, tag, text, bstate, istates):
        'Convert text content'
        if text or tag != 'br':
            bstate.content = True
        istate = istates[-1]
        para = bstate.para
        if tag in SPECIAL_TAGS and not text:
            para = para if para is not None else bstate.body
        elif para is None or tag in ('td', 'th'):
            body = bstate.body
            if bstate.pbreak:
                etree.SubElement(body, MBP('pagebreak'))
                bstate.pbreak = False
            bstate.istate = None
            bstate.anchor = None
            parent = bstate.nested[-1] if bstate.nested else bstate.body
            indent = istate.indent
            left = istate.left
            if isinstance(indent, basestring):
                indent = 0
            if indent < 0 and abs(indent) < left:
                left += indent
                indent = 0
            elif indent != 0 and abs(indent) < self.profile.fbase:
                indent = (indent / abs(indent)) * self.profile.fbase
            if tag in NESTABLE_TAGS and not istate.rendered:
                para = wrapper = etree.SubElement(
                    parent, XHTML(tag), attrib=istate.attrib)
                bstate.nested.append(para)
                if tag == 'li' and len(istates) > 1:
                    istates[-2].list_num += 1
                    para.attrib['value'] = str(istates[-2].list_num)
            elif tag in NESTABLE_TAGS and istate.rendered:
                para = wrapper = bstate.nested[-1]
            elif left > 0 and indent >= 0:
                ems = self.profile.mobi_ems_per_blockquote
                para = wrapper = etree.SubElement(parent, XHTML('blockquote'))
                para = wrapper
                emleft = int(round(left / self.profile.fbase)) - ems
                emleft = min((emleft, 10))
                while emleft > ems/2.0:
                    para = etree.SubElement(para, XHTML('blockquote'))
                    emleft -= ems
            else:
                para = wrapper = etree.SubElement(parent, XHTML('p'))
            bstate.inline = bstate.para = para
            vspace = bstate.vpadding + bstate.vmargin
            bstate.vpadding = bstate.vmargin = 0
            if tag not in TABLE_TAGS:
                wrapper.attrib['height'] = self.mobimlize_measure(vspace)
                para.attrib['width'] = self.mobimlize_measure(indent)
            elif tag == 'table' and vspace > 0:
                vspace = int(round(vspace / self.profile.fbase))
                while vspace > 0:
                    wrapper.addprevious(etree.Element(XHTML('br')))
                    vspace -= 1
            if istate.halign != 'auto' and isinstance(istate.halign, (str, unicode)):
                para.attrib['align'] = istate.halign
        istate.rendered = True
        pstate = bstate.istate
        if tag in CONTENT_TAGS:
            bstate.inline = para
            pstate = bstate.istate = None
            etree.SubElement(para, XHTML(tag), attrib=istate.attrib)
        elif tag in TABLE_TAGS:
            para.attrib['valign'] = 'top'
        if istate.ids:
            last = bstate.body[-1]
            for id in istate.ids:
                last.addprevious(etree.Element(XHTML('a'), attrib={'id': id}))
            istate.ids.clear()
        if not text:
            return
        if not pstate or istate != pstate:
            inline = para
            fsize = istate.fsize
            href = istate.href
            if not href:
                bstate.anchor = None
            elif pstate and pstate.href == href:
                inline = bstate.anchor
            else:
                inline = etree.SubElement(inline, XHTML('a'), href=href)
                bstate.anchor = inline

            if fsize != 3:
                inline = etree.SubElement(inline, XHTML('font'),
                                          size=str(fsize))
            if istate.family == 'monospace':
                inline = etree.SubElement(inline, XHTML('tt'))
            if istate.italic:
                inline = etree.SubElement(inline, XHTML('i'))
            if istate.bold:
                inline = etree.SubElement(inline, XHTML('b'))
            if istate.bgcolor is not None and istate.bgcolor != 'transparent' :
                inline = etree.SubElement(inline, XHTML('span'),
                        bgcolor=istate.bgcolor)
            if istate.fgcolor != 'black':
                inline = etree.SubElement(inline, XHTML('font'),
                        color=unicode(istate.fgcolor))
            if istate.strikethrough:
                inline = etree.SubElement(inline, XHTML('s'))
            if istate.underline:
                inline = etree.SubElement(inline, XHTML('u'))
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

    def mobimlize_elem(self, elem, stylizer, bstate, istates,
            ignore_valign=False):
        if not isinstance(elem.tag, basestring) \
           or namespace(elem.tag) != XHTML_NS:
            return
        style = stylizer.style(elem)
        # <mbp:frame-set/> does not exist lalalala
        if style['display'] in ('none', 'oeb-page-head', 'oeb-page-foot') \
           or style['visibility'] == 'hidden':
            return
        tag = barename(elem.tag)
        istate = copy.copy(istates[-1])
        istate.rendered = False
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
        elif not istate.href:
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
        istate.bgcolor  = style['background-color']
        istate.fgcolor  = style['color']
        istate.strikethrough = style['text-decoration'] == 'line-through'
        istate.underline = style['text-decoration'] == 'underline'
        if 'monospace' in style['font-family']:
            istate.family = 'monospace'
        elif 'sans-serif' in style['font-family']:
            istate.family = 'sans-serif'
        else:
            istate.family = 'serif'
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
                        try:
                            ems = int(round(float(value) / self.profile.fbase))
                        except:
                            continue
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
        if tag in TABLE_TAGS and self.ignore_tables:
            tag = 'span' if tag == 'td' else 'div'

        # GR: Added 'width', 'border' and 'scope'
        if tag in TABLE_TAGS:
            for attr in ('rowspan', 'colspan','width','border','scope'):
                if attr in elem.attrib:
                    istate.attrib[attr] = elem.attrib[attr]
        text = None
        if elem.text:
            if istate.preserve:
                text = elem.text
            elif len(elem) > 0 and elem.text.isspace():
                text = None
            else:
                text = COLLAPSE.sub(' ', elem.text)
        valign = style['vertical-align']
        not_baseline = valign in ('super', 'sub', 'text-top',
                'text-bottom')
        vtag = 'sup' if valign in ('super', 'text-top') else 'sub'
        if not_baseline and not ignore_valign and tag not in NOT_VTAGS and not isblock:
            nroot = etree.Element(XHTML('html'), nsmap=MOBI_NSMAP)
            vbstate = BlockState(etree.SubElement(nroot, XHTML('body')))
            vbstate.para = etree.SubElement(vbstate.body, XHTML('p'))
            self.mobimlize_elem(elem, stylizer, vbstate, istates,
                    ignore_valign=True)
            if len(istates) > 0:
                istates.pop()
            if len(istates) == 0:
                istates.append(FormatState())
            at_start = bstate.para is None
            if at_start:
                self.mobimlize_content('span', '', bstate, istates)
            parent = bstate.para if bstate.inline is None else bstate.inline
            if parent is not None:
                vtag = etree.SubElement(parent, XHTML(vtag))
                for child in vbstate.para:
                    vtag.append(child)
                return

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
                para.getparent().replace(para, etree.Element(XHTML('br')))
            bstate.para = None
            bstate.istate = None
            vmargin = asfloat(style['margin-bottom'])
            bstate.vmargin = max((bstate.vmargin, vmargin))
            vpadding = asfloat(style['padding-bottom'])
            if vpadding > 0:
                bstate.vpadding += bstate.vmargin
                bstate.vmargin = 0
                bstate.vpadding += vpadding
        if bstate.nested and bstate.nested[-1].tag == elem.tag:
            bstate.nested.pop()
        istates.pop()
