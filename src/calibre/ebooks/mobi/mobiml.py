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
from calibre.ebooks.oeb.base import XHTML, XHTML_NS, urlnormalize
from calibre.ebooks.oeb.stylizer import Stylizer
from calibre.ebooks.oeb.transforms.flatcss import KeyMapper
from calibre.utils.magick.draw import identify_data

MBP_NS = 'http://mobipocket.com/ns/mbp'
def MBP(name):
    return '{%s}%s' % (MBP_NS, name)

MOBI_NSMAP = {None: XHTML_NS, 'mbp': MBP_NS}

HEADER_TAGS = set(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
# GR: Added 'caption' to both sets
NESTABLE_TAGS = set(['ol', 'ul', 'li', 'table', 'tr', 'td', 'th', 'caption'])
TABLE_TAGS = set(['table', 'tr', 'td', 'th', 'caption'])

SPECIAL_TAGS = set(['hr', 'br'])
CONTENT_TAGS = set(['img', 'hr', 'br'])

NOT_VTAGS = HEADER_TAGS | NESTABLE_TAGS | TABLE_TAGS | SPECIAL_TAGS | \
    CONTENT_TAGS
LEAF_TAGS = set(['base', 'basefont', 'frame', 'link', 'meta', 'area', 'br',
'col', 'hr', 'img', 'input', 'param'])
PAGE_BREAKS = set(['always', 'left', 'right'])

COLLAPSE = re.compile(r'[ \t\r\n\v]+')

def asfloat(value):
    if not isinstance(value, (int, long, float)):
        return 0.0
    return float(value)

def isspace(text):
    if not text:
        return True
    if u'\xa0' in text:
        return False
    return text.isspace()

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
        self.log = self.oeb.logger
        self.opts = context
        self.profile = profile = context.dest
        self.fnums = fnums = dict((v, k) for k, v in profile.fnums.items())
        self.fmap = KeyMapper(profile.fbase, profile.fbase, fnums.keys())
        self.mobimlize_spine()

    def mobimlize_spine(self):
        'Iterate over the spine and convert it to MOBIML'
        for item in self.oeb.spine:
            stylizer = Stylizer(item.data, item.href, self.oeb, self.opts, self.profile)
            body = item.data.find(XHTML('body'))
            nroot = etree.Element(XHTML('html'), nsmap=MOBI_NSMAP)
            nbody = etree.SubElement(nroot, XHTML('body'))
            self.current_spine_item = item
            self.mobimlize_elem(body, stylizer, BlockState(nbody),
                                [FormatState()])
            item.data = nroot
            #print etree.tostring(nroot)

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
            elif not self.opts.mobi_ignore_margins and left > 0 and indent >= 0:
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
                if tag in ('ul', 'ol') and vspace > 0:
                    wrapper.addprevious(etree.Element(XHTML('div'),
                        height=self.mobimlize_measure(vspace)))
                else:
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
            try:
                etree.SubElement(para, XHTML(tag), attrib=istate.attrib)
            except:
                print 'Invalid subelement:', para, tag, istate.attrib
                raise
        elif tag in TABLE_TAGS:
            para.attrib['valign'] = 'top'
        if istate.ids:
            for id_ in istate.ids:
                anchor = etree.Element(XHTML('a'), attrib={'id': id_})
                if tag == 'li':
                    try:
                        last = bstate.body[-1][-1]
                    except:
                        break
                    last.insert(0, anchor)
                    anchor.tail = last.text
                    last.text = None
                else:
                    last = bstate.body[-1]
                    # We use append instead of addprevious so that inline
                    # anchors in large blocks point to the correct place. See
                    # https://bugs.launchpad.net/calibre/+bug/899831
                    # This could potentially break if inserting an anchor at
                    # this point in the markup is illegal, but I cannot think
                    # of such a case offhand.
                    if barename(last.tag) in LEAF_TAGS:
                        last.addprevious(anchor)
                    else:
                        last.append(anchor)

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
            id_ = elem.get('id', None)
            if id_:
                # Keep anchors so people can use display:none
                # to generate hidden TOCs
                tail = elem.tail
                elem.clear()
                elem.text = None
                elem.set('id', id_)
                elem.tail = tail
                elem.tag = XHTML('a')
            else:
                return
        tag = barename(elem.tag)
        istate = copy.copy(istates[-1])
        istate.rendered = False
        istate.list_num = 0
        if tag == 'ol' and 'start' in elem.attrib:
            try:
                istate.list_num = int(elem.attrib['start'])-1
            except:
                pass
        istates.append(istate)
        left = 0
        display = style['display']
        if display == 'table-cell':
            display = 'inline'
        elif display.startswith('table'):
            display = 'block'
        isblock = (not display.startswith('inline') and style['display'] !=
                'none')
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
        istate.strikethrough = style.effective_text_decoration == 'line-through'
        istate.underline = style.effective_text_decoration == 'underline'
        ff = style['font-family'].lower() if style['font-family'] else ''
        if 'monospace' in ff or 'courier' in ff or ff.endswith(' mono'):
            istate.family = 'monospace'
        elif ('sans-serif' in ff or 'sansserif' in ff or 'verdana' in ff or
                'arial' in ff or 'helvetica' in ff):
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
            cssdict = style.cssdict()
            valign = cssdict.get('vertical-align', None)
            if valign in ('top', 'bottom', 'middle'):
                istate.attrib['align'] = valign
            for prop in ('width', 'height'):
                if cssdict[prop] != 'auto':
                    value = style[prop]
                    if value == getattr(self.profile, prop):
                        result = '100%'
                    else:
                        # Amazon's renderer does not support
                        # img sizes in units other than px
                        # See #7520 for test case
                        try:
                            pixs = int(round(float(value) /
                                (72./self.profile.dpi)))
                        except:
                            continue
                        result = str(pixs)
                    istate.attrib[prop] = result
            if 'width' not in istate.attrib or 'height' not in istate.attrib:
                href = self.current_spine_item.abshref(elem.attrib['src'])
                try:
                    item = self.oeb.manifest.hrefs[urlnormalize(href)]
                except:
                    self.oeb.logger.warn('Failed to find image:',
                            href)
                else:
                    try:
                        width, height = identify_data(item.data)[:2]
                    except:
                        self.oeb.logger.warn('Invalid image:', href)
                    else:
                        if 'width' not in istate.attrib and 'height' not in \
                                    istate.attrib:
                            istate.attrib['width'] = str(width)
                            istate.attrib['height'] = str(height)
                        else:
                            ar = float(width)/float(height)
                            if 'width' not in istate.attrib:
                                try:
                                    width = int(istate.attrib['height'])*ar
                                except:
                                    pass
                                istate.attrib['width'] = str(int(width))
                            else:
                                try:
                                    height = int(istate.attrib['width'])/ar
                                except:
                                    pass
                                istate.attrib['height'] = str(int(height))
                        item.unload_data_from_memory()
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

        if tag in ('table', 'td', 'tr'):
            col = style.backgroundColor
            if col:
                elem.set('bgcolor', col)
            css = style.cssdict()
            if 'border' in css or 'border-width' in css:
                elem.set('border', '1')
        if tag in TABLE_TAGS:
            for attr in ('rowspan', 'colspan', 'width', 'border', 'scope',
                    'bgcolor'):
                if attr in elem.attrib:
                    istate.attrib[attr] = elem.attrib[attr]
        if tag == 'q':
            t = elem.text
            if not t:
                t = ''
            elem.text = u'\u201c' + t
            t = elem.tail
            if not t:
                t = ''
            elem.tail = u'\u201d' + t
        text = None
        if elem.text:
            if istate.preserve:
                text = elem.text
            else:
                text = COLLAPSE.sub(' ', elem.text)
        valign = style['vertical-align']
        not_baseline = valign in ('super', 'sub', 'text-top',
                'text-bottom', 'top', 'bottom') or (
                isinstance(valign, (float, int)) and abs(valign) != 0)
        issup = valign in ('super', 'text-top', 'top') or (
            isinstance(valign, (float, int)) and valign > 0)
        vtag = 'sup' if issup else 'sub'
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
                vtag = etree.SubElement(vtag, XHTML('small'))
                # Add anchors
                for child in vbstate.body:
                    if child is not vbstate.para:
                        vtag.append(child)
                    else:
                        break
                if vbstate.para is not None:
                    for child in vbstate.para:
                        vtag.append(child)
                return

        if tag == 'blockquote':
            old_mim = self.opts.mobi_ignore_margins
            self.opts.mobi_ignore_margins = False

        if (text or tag in CONTENT_TAGS or tag in NESTABLE_TAGS or (
            # We have an id but no text and no children, the id should still
            # be added.
            istate.ids and tag in ('a', 'span', 'i', 'b', 'u') and
            len(elem)==0)):
            self.mobimlize_content(tag, text, bstate, istates)
        for child in elem:
            self.mobimlize_elem(child, stylizer, bstate, istates)
            tail = None
            if child.tail:
                if istate.preserve:
                    tail = child.tail
                elif bstate.para is None and isspace(child.tail):
                    tail = None
                else:
                    tail = COLLAPSE.sub(' ', child.tail)
            if tail:
                self.mobimlize_content(tag, tail, bstate, istates)

        if tag == 'blockquote':
            self.opts.mobi_ignore_margins = old_mim

        if bstate.content and style['page-break-after'] in PAGE_BREAKS:
            bstate.pbreak = True
        if isblock:
            para = bstate.para
            if para is not None and para.text == u'\xa0' and len(para) < 1:
                if style.height > 2:
                    para.getparent().replace(para, etree.Element(XHTML('br')))
                else:
                    # This is too small to be rendered effectively, drop it
                    para.getparent().remove(para)
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
