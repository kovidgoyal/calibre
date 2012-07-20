# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Transform OEB content into PML markup
'''

import re

from lxml import etree

from calibre.ebooks.pdb.ereader import image_name
from calibre.ebooks.pml import unipmlcode

TAG_MAP = {
    'b'       : 'B',
    'strong'  : 'B',
    'i'       : 'i',
    'small'   : 'k',
    'sub'     : 'Sb',
    'sup'     : 'Sp',
    'big'     : 'l',
    'del'     : 'o',
    'h1'      : 'x',
    'h2'      : 'X0',
    'h3'      : 'X1',
    'h4'      : 'X2',
    'h5'      : 'X3',
    'h6'      : 'X4',
    '!--'     : 'v',
}

STYLES = [
    ('font-weight', {'bold' : 'B', 'bolder' : 'B'}),
    ('font-style', {'italic' : 'i'}),
    ('text-decoration', {'underline' : 'u'}),
    ('text-align', {'right' : 'r', 'center' : 'c'}),
]

BLOCK_TAGS = [
    'p',
    'div',
]

BLOCK_STYLES = [
    'block',
]

LINK_TAGS = [
    'a',
]

IMAGE_TAGS = [
    'img',
]

SEPARATE_TAGS = [
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'hr',
    'img',
    'li',
    'tr',
]

class PMLMLizer(object):
    def __init__(self, log):
        self.log = log
        self.image_hrefs = {}
        self.link_hrefs = {}

    def extract_content(self, oeb_book, opts):
        self.log.info('Converting XHTML to PML markup...')
        self.oeb_book = oeb_book
        self.opts = opts

        # This is used for adding \CX tags chapter markers. This is separate
        # from the optional inline toc.
        self.toc = {}
        self.create_flat_toc(self.oeb_book.toc)

        return self.pmlmlize_spine()

    def create_flat_toc(self, nodes, level=0):
        for item in nodes:
            href, mid, id = item.href.partition('#')
            self.get_anchor_id(href, id)
            if not self.toc.get(href, None):
                self.toc[href] = {}
            self.toc[href][id] = (item.title, level)
            self.create_flat_toc(item.nodes, level + 1)

    def pmlmlize_spine(self):
        self.image_hrefs = {}
        self.link_hrefs = {}
        output = [u'']
        output.append(self.get_cover_page())
        output.append(self.get_text())
        output = ''.join(output)
        output = self.clean_text(output)
        return output

    def get_cover_page(self):
        from calibre.ebooks.oeb.stylizer import Stylizer
        from calibre.ebooks.oeb.base import XHTML

        output = u''
        if 'cover' in self.oeb_book.guide:
            output += '\\m="cover.png"\n'
            self.image_hrefs[self.oeb_book.guide['cover'].href] = 'cover.png'
        if 'titlepage' in self.oeb_book.guide:
            self.log.debug('Generating title page...')
            href = self.oeb_book.guide['titlepage'].href
            item = self.oeb_book.manifest.hrefs[href]
            if item.spine_position is None:
                stylizer = Stylizer(item.data, item.href, self.oeb_book,
                        self.opts, self.opts.output_profile)
                output += ''.join(self.dump_text(item.data.find(XHTML('body')), stylizer, item))
        return output

    def get_text(self):
        from calibre.ebooks.oeb.stylizer import Stylizer
        from calibre.ebooks.oeb.base import XHTML

        text = [u'']
        for item in self.oeb_book.spine:
            self.log.debug('Converting %s to PML markup...' % item.href)
            content = unicode(etree.tostring(item.data, encoding=unicode))
            content = self.prepare_text(content)
            content = etree.fromstring(content)
            stylizer = Stylizer(content, item.href, self.oeb_book, self.opts, self.opts.output_profile)
            text.append(self.add_page_anchor(item))
            text += self.dump_text(content.find(XHTML('body')), stylizer, item)
        return ''.join(text)

    def add_page_anchor(self, page):
        return self.get_anchor(page, '')

    def get_anchor_id(self, href, aid):
        aid = '%s#%s' % (href, aid)
        if aid not in self.link_hrefs.keys():
            self.link_hrefs[aid] = 'calibre_link-%s' % len(self.link_hrefs.keys())
        aid = self.link_hrefs[aid]
        return aid

    def get_anchor(self, page, aid):
        aid = self.get_anchor_id(page.href, aid)
        return u'\\Q="%s"' % aid

    def remove_newlines(self, text):
        text = text.replace('\r\n', ' ')
        text = text.replace('\n', ' ')
        text = text.replace('\r', ' ')
        return text

    def prepare_string_for_pml(self, text):
        text = self.remove_newlines(text)
        # Replace \ with \\ so \ in the text is not interperted as
        # a pml code.
        text = text.replace('\\', '\\\\')
        # Replace sequences of \\c \\c with pml sequences denoting
        # empty lines.
        text = text.replace('\\\\c \\\\c', '\\c \n\\c\n')
        return text

    def prepare_text(self, text):
        # Replace empty paragraphs with \c pml codes used to denote emtpy lines.
        text = re.sub(ur'(?<=</p>)\s*<p[^>]*>[\xc2\xa0\s]*</p>', '\\c\n\\c', text)
        return text

    def clean_text(self, text):
        # Remove excessive \p tags
        text = re.sub(r'\\p\s*\\p', '', text)

        # Remove anchors that do not have links
        anchors = set(re.findall(r'(?<=\\Q=").+?(?=")', text))
        links = set(re.findall(r'(?<=\\q="#).+?(?=")', text))
        for unused in anchors.difference(links):
            text = text.replace('\\Q="%s"' % unused, '')

        # Remove \Cn tags that are within \x and \Xn tags
        text = re.sub(ur'(?msu)(?P<t>\\(x|X[0-4]))(?P<a>.*?)(?P<c>\\C[0-4]\s*=\s*"[^"]*")(?P<b>.*?)(?P=t)', '\g<t>\g<a>\g<b>\g<t>', text)

        # Replace bad characters.
        text = text.replace(u'\xc2', '')
        text = text.replace(u'\xa0', ' ')

        # Turn all characters that cannot be represented by themself into their
        # PML code equivelent
        text = re.sub('[^\x00-\x7f]', lambda x: unipmlcode(x.group()), text)

        # Remove excess spaces at beginning and end of lines
        text = re.sub('(?m)^[ ]+', '', text)
        text = re.sub('(?m)[ ]+$', '', text)

        # Remove excessive spaces
        text = re.sub('[ ]{2,}', ' ', text)

        # Condense excessive \c empty line sequences.
        text = re.sub('(\\c\s*\\c\s*){2,}', '\\c \n\\c\n', text)

        # Remove excessive newlines.
        text = re.sub('\n[ ]+\n', '\n\n', text)
        if self.opts.remove_paragraph_spacing:
            text = re.sub('\n{2,}', '\n', text)
            # Only indent lines that don't have special formatting
            text = re.sub('(?imu)^(?P<text>.+)$', lambda mo: mo.group('text') if re.search(r'\\[XxCmrctTp]', mo.group('text')) else '        %s' % mo.group('text'), text)
        else:
            text = re.sub('\n{3,}', '\n\n', text)

        return text

    def dump_text(self, elem, stylizer, page, tag_stack=[]):
        from calibre.ebooks.oeb.base import XHTML_NS, barename, namespace

        if not isinstance(elem_tree.tag, basestring) or namespace(elem_tree.tag) != XHTML_NS:
            p = elem.getparent()
            if p is not None and isinstance(p.tag, basestring) and namespace(p.tag) == XHTML_NS \
                    and elem.tail:
                return [elem.tail]
            return []

        text = []
        tags = []
        style = stylizer.style(elem)

        if style['display'] in ('none', 'oeb-page-head', 'oeb-page-foot') \
           or style['visibility'] == 'hidden':
            if hasattr(elem, 'tail') and elem.tail:
                return [elem.tail]
            return []

        tag = barename(elem.tag)

        # Are we in a paragraph block?
        if tag in BLOCK_TAGS or style['display'] in BLOCK_STYLES:
            tags.append('block')

        # Process tags that need special processing and that do not have inner
        # text. Usually these require an argument.
        if tag in IMAGE_TAGS:
            if elem.attrib.get('src', None):
                if page.abshref(elem.attrib['src']) not in self.image_hrefs.keys():
                    if len(self.image_hrefs.keys()) == 0:
                        self.image_hrefs[page.abshref(elem.attrib['src'])] = 'cover.png'
                    else:
                        self.image_hrefs[page.abshref(elem.attrib['src'])] = image_name('%s.png' % len(self.image_hrefs.keys()), self.image_hrefs.keys()).strip('\x00')
                text.append('\\m="%s"' % self.image_hrefs[page.abshref(elem.attrib['src'])])
        elif tag == 'hr':
            w = '\\w'
            width = elem.get('width')
            if width:
                if not width.endswith('%'):
                    width += '%'
                w += '="%s"' % width
            else:
                w += '="50%"'
            text.append(w)
        elif tag == 'br':
            text.append('\n\\c \n\\c\n')

        # TOC markers.
        toc_name = elem.attrib.get('name', None)
        toc_id = elem.attrib.get('id', None)
        # Only write the TOC marker if the tag isn't a heading and we aren't in one.
        if (toc_id or toc_name) and tag not in ('h1', 'h2','h3','h4','h5','h6') and \
            'x' not in tag_stack+tags and 'X0' not in tag_stack+tags and \
            'X1' not in tag_stack+tags and 'X2' not in tag_stack+tags and \
            'X3' not in tag_stack+tags and 'X4' not in tag_stack+tags:

            toc_page = page.href
            if self.toc.get(toc_page, None):
                for toc_x in (toc_name, toc_id):
                    toc_title, toc_depth = self.toc[toc_page].get(toc_x, (None, 0))
                    if toc_title:
                        toc_depth = max(min(toc_depth, 4), 0)
                        text.append('\\C%s="%s"' % (toc_depth, toc_title))

        # Process style information that needs holds a single tag.
        # Commented out because every page in an OEB book starts with this style.
        if style['page-break-before'] == 'always':
            text.append('\\p')

        # Process basic PML tags.
        pml_tag = TAG_MAP.get(tag, None)
        if pml_tag and pml_tag not in tag_stack+tags:
            text.append('\\%s' % pml_tag)
            tags.append(pml_tag)

        # Special processing of tags that require an argument.
        # Anchors links
        if tag in LINK_TAGS and 'q' not in tag_stack+tags:
            href = elem.get('href')
            if href:
                href = page.abshref(href)
                if '://' not in href:
                    if '#' not in href:
                        href += '#'
                    if href not in self.link_hrefs.keys():
                        self.link_hrefs[href] = 'calibre_link-%s' % len(self.link_hrefs.keys())
                    href = '#%s' % self.link_hrefs[href]
                    text.append('\\q="%s"' % href)
                    tags.append('q')

        # Anchor ids
        id_name = elem.get('id')
        name_name = elem.get('name')
        for name_x in (id_name, name_name):
            if name_x:
                text.append(self.get_anchor(page, name_x))

        # Processes style information
        for s in STYLES:
            style_tag = s[1].get(style[s[0]], None)
            if style_tag and style_tag not in tag_stack+tags:
                text.append('\\%s' % style_tag)
                tags.append(style_tag)

        # margin left
        try:
            mms = int(float(style['margin-left']) * 100 / style.height)
            if mms:
                text.append('\\T="%s%%"' % mms)
        except:
            pass

        # Soft scene breaks.
        try:
            ems = int(round((float(style.marginTop) / style.fontSize) - 1))
            if ems >= 1:
                text.append('\n\\c \n\\c\n')
        except:
            pass

        # Proccess text within this tag.
        if hasattr(elem, 'text') and elem.text:
            text.append(self.prepare_string_for_pml(elem.text))

        # Process inner tags
        for item in elem:
            text += self.dump_text(item, stylizer, page, tag_stack+tags)

        # Close opened tags.
        tags.reverse()
        text += self.close_tags(tags)

        #if tag in SEPARATE_TAGS:
        #    text.append('\n\n')

        if style['page-break-after'] == 'always':
            text.append('\\p')

        # Process text after this tag but not within another.
        if hasattr(elem, 'tail') and elem.tail:
            text.append(self.prepare_string_for_pml(elem.tail))

        return text

    def close_tags(self, tags):
        text = []
        for tag in tags:
            # block isn't a real tag we just use
            # it to determine when we need to start
            # a new text block.
            if tag == 'block':
                text.append('\n\n')
            else:
                # closing \c and \r need to be placed
                # on the next line per PML spec.
                if tag in ('c', 'r'):
                    text.append('\n\\%s' % tag)
                else:
                    text.append('\\%s' % tag)
        return text
