#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import io
import os
import re
import shutil
import struct
import textwrap
from lxml import etree, html

from calibre import entity_to_unicode, guess_type, xml_entity_to_unicode
from calibre.ebooks import DRMError, unit_convert
from calibre.ebooks.chardet import strip_encoding_declarations
from calibre.ebooks.compression.palmdoc import decompress_doc
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata.opf2 import OPF, OPFCreator
from calibre.ebooks.metadata.toc import TOC
from calibre.ebooks.mobi import MobiError
from calibre.ebooks.mobi.huffcdic import HuffReader
from calibre.ebooks.mobi.reader.headers import BookHeader
from calibre.utils.cleantext import clean_ascii_chars, clean_xml_chars
from calibre.utils.img import AnimatedGIF, gif_data_to_png_data, save_cover_data_to
from calibre.utils.imghdr import what
from calibre.utils.logging import default_log
from polyglot.builtins import iteritems


class TopazError(ValueError):
    pass


class KFXError(ValueError):

    def __init__(self):
        ValueError.__init__(self, _(
            'This is an Amazon KFX book. It cannot be processed.'
            ' See {} for information on how to handle KFX books.'
        ).format('https://www.mobileread.com/forums/showthread.php?t=283371'))


class MobiReader:
    PAGE_BREAK_PAT = re.compile(
        r'<\s*/{0,1}\s*mbp:pagebreak((?:\s+[^/>]*){0,1})/{0,1}\s*>\s*(?:<\s*/{0,1}\s*mbp:pagebreak\s*/{0,1}\s*>)*',
        re.IGNORECASE)
    IMAGE_ATTRS = ('lowrecindex', 'recindex', 'hirecindex')

    def __init__(self, filename_or_stream, log=None, user_encoding=None, debug=None,
            try_extra_data_fix=False):
        self.log = log or default_log
        self.debug = debug
        self.embedded_mi = None
        self.warned_about_trailing_entry_corruption = False
        self.base_css_rules = textwrap.dedent('''
                body { text-align: justify }

                blockquote { margin: 0em 0em 0em 2em; }

                p { margin: 0em; text-indent: 1.5em }

                .bold { font-weight: bold }

                .italic { font-style: italic }

                .underline { text-decoration: underline }

                .mbp_pagebreak {
                    page-break-after: always; margin: 0; display: block
                }
                ''')
        self.tag_css_rules = {}
        self.left_margins = {}
        self.text_indents = {}

        if hasattr(filename_or_stream, 'read'):
            stream = filename_or_stream
            stream.seek(0)
        else:
            stream = open(filename_or_stream, 'rb')

        raw = stream.read()
        if raw.startswith(b'TPZ'):
            raise TopazError(_('This is an Amazon Topaz book. It cannot be processed.'))
        if raw.startswith(b'\xeaDRMION\xee'):
            raise KFXError()

        self.header   = raw[0:72]
        self.name     = self.header[:32].replace(b'\x00', b'')
        self.num_sections, = struct.unpack('>H', raw[76:78])

        self.ident = self.header[0x3C:0x3C + 8].upper()
        if self.ident not in (b'BOOKMOBI', b'TEXTREAD'):
            raise MobiError('Unknown book type: %s' % repr(self.ident))

        self.sections = []
        self.section_headers = []
        for i in range(self.num_sections):
            offset, a1, a2, a3, a4 = struct.unpack('>LBBBB', raw[78 + i * 8:78 + i * 8 + 8])
            flags, val = a1, a2 << 16 | a3 << 8 | a4
            self.section_headers.append((offset, flags, val))

        def section(section_number):
            if section_number == self.num_sections - 1:
                end_off = len(raw)
            else:
                end_off = self.section_headers[section_number + 1][0]
            off = self.section_headers[section_number][0]
            return raw[off:end_off]

        for i in range(self.num_sections):
            self.sections.append((section(i), self.section_headers[i]))

        self.book_header = bh = BookHeader(self.sections[0][0], self.ident,
            user_encoding, self.log, try_extra_data_fix=try_extra_data_fix)
        self.name = self.name.decode(self.book_header.codec, 'replace')
        self.kf8_type = None
        k8i = getattr(self.book_header.exth, 'kf8_header', None)

        # Ancient PRC files from Baen can have random values for
        # mobi_version, so be conservative
        if (self.book_header.mobi_version == 8 and hasattr(self.book_header,
            'skelidx')):
            self.kf8_type = 'standalone'
        elif k8i is not None:  # Check for joint mobi 6 and kf 8 file
            try:
                raw = self.sections[k8i-1][0]
            except:
                raw = None
            if raw == b'BOUNDARY':
                try:
                    self.book_header = BookHeader(self.sections[k8i][0],
                            self.ident, user_encoding, self.log)
                    self.book_header.kf8_first_image_index = self.book_header.first_image_index + k8i
                    self.book_header.mobi6_records = bh.records

                    # Need the first_image_index from the mobi 6 header as well
                    for x in ('first_image_index',):
                        setattr(self.book_header, x, getattr(bh, x))

                    # We need to do this because the MOBI 6 text extract code
                    # does not know anything about the kf8 offset
                    if hasattr(self.book_header, 'huff_offset'):
                        self.book_header.huff_offset += k8i

                    self.kf8_type = 'joint'
                    self.kf8_boundary = k8i-1
                except:
                    self.book_header = bh

    def check_for_drm(self):
        if self.book_header.encryption_type != 0:
            try:
                name = self.book_header.exth.mi.title
            except:
                name = self.name
            if not name:
                name = self.name
            raise DRMError(name)

    def extract_content(self, output_dir, parse_cache):
        output_dir = os.path.abspath(output_dir)
        self.check_for_drm()
        processed_records = self.extract_text()
        if self.debug is not None:
            parse_cache['calibre_raw_mobi_markup'] = self.mobi_html
        self.add_anchors()
        self.processed_html = self.processed_html.decode(self.book_header.codec,
            'ignore')
        self.processed_html = self.processed_html.replace('</</', '</')
        self.processed_html = re.sub(r'</([a-zA-Z]+)<', r'</\1><',
                self.processed_html)
        self.processed_html = self.processed_html.replace('\ufeff', '')
        # Remove tags of the form <xyz: ...> as they can cause issues further
        # along the pipeline
        self.processed_html = re.sub(r'</{0,1}[a-zA-Z]+:\s+[^>]*>', '',
                self.processed_html)

        self.processed_html = strip_encoding_declarations(self.processed_html)
        self.processed_html = re.sub(r'&(\S+?);', xml_entity_to_unicode,
            self.processed_html)
        image_name_map = self.extract_images(processed_records, output_dir)
        self.replace_page_breaks()
        self.cleanup_html()

        self.log.debug('Parsing HTML...')
        self.processed_html = clean_xml_chars(self.processed_html)
        try:
            root = html.fromstring(self.processed_html)
            if len(root.xpath('//html')) > 5:
                root = html.fromstring(self.processed_html.replace('\x0c',
                    '').replace('\x14', ''))
        except Exception:
            self.log.warning('MOBI markup appears to contain random bytes. Stripping.')
            self.processed_html = self.remove_random_bytes(self.processed_html)
            try:
                root = html.fromstring(self.processed_html)
            except Exception:
                self.log.warning('MOBI markup could not be parsed by lxml using html5-parser')
                # Happens on windows with python 3 where lxml causes libxml to die with an
                # error about using UCS-4 little endian encoding if certain
                # characters are present in the input
                from html5_parser import parse
                root = parse(self.processed_html, keep_doctype=False, namespace_elements=False, maybe_xhtml=False, sanitize_names=True)
        if root.xpath('descendant::p/descendant::p'):
            from html5_parser import parse
            self.log.warning('Malformed markup, parsing using html5-parser')
            self.processed_html = strip_encoding_declarations(self.processed_html)
            # These trip up the html5 parser causing all content to be placed
            # under the <guide> tag
            self.processed_html = re.sub(r'<metadata>.+?</metadata>', '', self.processed_html, flags=re.I)
            self.processed_html = re.sub(r'<guide>.+?</guide>', '', self.processed_html, flags=re.I)
            try:
                root = parse(self.processed_html, maybe_xhtml=False, keep_doctype=False, sanitize_names=True)
            except Exception:
                self.log.warning('MOBI markup appears to contain random bytes. Stripping.')
                self.processed_html = self.remove_random_bytes(self.processed_html)
                root = parse(self.processed_html, maybe_xhtml=False, keep_doctype=False, sanitize_names=True)
            if len(root.xpath('body/descendant::*')) < 1:
                # There are probably stray </html>s in the markup
                self.processed_html = self.processed_html.replace('</html>',
                        '')
                root = parse(self.processed_html, maybe_xhtml=False, keep_doctype=False, sanitize_names=True)

        if root.tag != 'html':
            self.log.warn('File does not have opening <html> tag')
            nroot = html.fromstring('<html><head></head><body></body></html>')
            bod = nroot.find('body')
            for child in list(root):
                child.getparent().remove(child)
                bod.append(child)
            root = nroot

        htmls = list(root.xpath('//html'))

        if len(htmls) > 1:
            self.log.warn('Markup contains multiple <html> tags, merging.')
            # Merge all <head> and <body> sections
            for h in htmls:
                p = h.getparent()
                if hasattr(p, 'remove'):
                    p.remove(h)
            bodies, heads = root.xpath('//body'), root.xpath('//head')
            for x in root:
                root.remove(x)
            head, body = map(root.makeelement, ('head', 'body'))
            for h in heads:
                for x in h:
                    h.remove(x)
                    head.append(x)
            for b in bodies:
                for x in b:
                    b.remove(x)
                    body.append(x)
            root.append(head), root.append(body)
        for x in root.xpath('//script'):
            x.getparent().remove(x)

        head = root.xpath('//head')
        if head:
            head = head[0]
        else:
            head = root.makeelement('head', {})
            root.insert(0, head)
        head.text = '\n\t'
        link = head.makeelement('link', {'type':'text/css',
            'href':'styles.css', 'rel':'stylesheet'})
        head.insert(0, link)
        link.tail = '\n\t'
        title = head.xpath('descendant::title')
        m = head.makeelement('meta', {'http-equiv':'Content-Type',
            'content':'text/html; charset=utf-8'})
        head.insert(0, m)
        if not title:
            title = head.makeelement('title', {})
            try:
                title.text = self.book_header.title
            except ValueError:
                title.text = clean_ascii_chars(self.book_header.title)
            title.tail = '\n\t'
            head.insert(0, title)
            head.text = '\n\t'

        self.upshift_markup(root, image_name_map)
        guides = root.xpath('//guide')
        guide = guides[0] if guides else None
        metadata_elems = root.xpath('//metadata')
        if metadata_elems and self.book_header.exth is None:
            self.read_embedded_metadata(root, metadata_elems[0], guide)
        for elem in guides + metadata_elems:
            elem.getparent().remove(elem)
        htmlfile = os.path.join(output_dir, 'index.html')
        try:
            for ref in guide.xpath('descendant::reference'):
                if 'href' in ref.attrib:
                    ref.attrib['href'] = os.path.basename(htmlfile) + ref.attrib['href']
        except AttributeError:
            pass

        def write_as_utf8(path, data):
            if isinstance(data, str):
                data = data.encode('utf-8')
            with lopen(path, 'wb') as f:
                f.write(data)

        parse_cache[htmlfile] = root
        self.htmlfile = htmlfile
        ncx = io.BytesIO()
        opf, ncx_manifest_entry = self.create_opf(htmlfile, guide, root)
        self.created_opf_path = os.path.splitext(htmlfile)[0] + '.opf'
        opf.render(lopen(self.created_opf_path, 'wb'), ncx,
            ncx_manifest_entry=ncx_manifest_entry)
        ncx = ncx.getvalue()
        if ncx:
            ncx_path = os.path.join(os.path.dirname(htmlfile), 'toc.ncx')
            write_as_utf8(ncx_path, ncx)

        css = [self.base_css_rules, '\n\n']
        for cls, rule in self.tag_css_rules.items():
            css.append(f'.{cls} {{ {rule} }}\n\n')
        write_as_utf8('styles.css', ''.join(css))

        if self.book_header.exth is not None or self.embedded_mi is not None:
            self.log.debug('Creating OPF...')
            ncx = io.BytesIO()
            opf, ncx_manifest_entry  = self.create_opf(htmlfile, guide, root)
            opf.render(open(os.path.splitext(htmlfile)[0] + '.opf', 'wb'), ncx,
                ncx_manifest_entry)
            ncx = ncx.getvalue()
            if ncx:
                write_as_utf8(os.path.splitext(htmlfile)[0] + '.ncx', ncx)

    def read_embedded_metadata(self, root, elem, guide):
        raw = b'<?xml version="1.0" encoding="utf-8" ?>\n<package>' + \
                html.tostring(elem, encoding='utf-8') + b'</package>'
        stream = io.BytesIO(raw)
        opf = OPF(stream)
        self.embedded_mi = opf.to_book_metadata()
        if guide is not None:
            for ref in guide.xpath('descendant::reference'):
                if 'cover' in ref.get('type', '').lower():
                    href = ref.get('href', '')
                    if href.startswith('#'):
                        href = href[1:]
                    anchors = root.xpath('//*[@id="%s"]' % href)
                    if anchors:
                        cpos = anchors[0]
                        reached = False
                        for elem in root.iter():
                            if elem is cpos:
                                reached = True
                            if reached and elem.tag == 'img':
                                cover = elem.get('src', None)
                                self.embedded_mi.cover = cover
                                elem.getparent().remove(elem)
                                break
                    break

    def cleanup_html(self):
        self.log.debug('Cleaning up HTML...')
        self.processed_html = re.sub(r'<div height="0(pt|px|ex|em|%){0,1}"></div>', '', self.processed_html)
        if self.book_header.ancient and b'<html' not in self.mobi_html[:300].lower():
            self.processed_html = '<html><p>' + self.processed_html.replace('\n\n', '<p>') + '</html>'
        self.processed_html = self.processed_html.replace('\r\n', '\n')
        self.processed_html = self.processed_html.replace('> <', '>\n<')
        self.processed_html = self.processed_html.replace('<mbp: ', '<mbp:')
        self.processed_html = re.sub(r'<\?xml[^>]*>', '', self.processed_html)
        self.processed_html = re.sub(r'<\s*(/?)\s*o:p[^>]*>', r'', self.processed_html)
        # Swap inline and block level elements, and order block level elements according to priority
        # - lxml and beautifulsoup expect/assume a specific order based on xhtml spec
        self.processed_html = re.sub(
            r'(?i)(?P<styletags>(<(h\d+|i|b|u|em|small|big|strong|tt)>\s*){1,})(?P<para><p[^>]*>)', r'\g<para>'+r'\g<styletags>', self.processed_html)
        self.processed_html = re.sub(
            r'(?i)(?P<para></p[^>]*>)\s*(?P<styletags>(</(h\d+|i|b|u|em|small|big|strong|tt)>\s*){1,})', r'\g<styletags>'+r'\g<para>', self.processed_html)
        self.processed_html = re.sub(
            r'(?i)(?P<blockquote>(</(blockquote|div)[^>]*>\s*){1,})(?P<para></p[^>]*>)', r'\g<para>'+r'\g<blockquote>', self.processed_html)
        self.processed_html = re.sub(
            r'(?i)(?P<para><p[^>]*>)\s*(?P<blockquote>(<(blockquote|div)[^>]*>\s*){1,})', r'\g<blockquote>'+r'\g<para>', self.processed_html)
        bods = htmls = 0
        for x in re.finditer('</body>|</html>', self.processed_html):
            if x == '</body>':
                bods +=1
            else:
                htmls += 1
            if bods > 1 and htmls > 1:
                break
        if bods > 1:
            self.processed_html = self.processed_html.replace('</body>', '')
        if htmls > 1:
            self.processed_html = self.processed_html.replace('</html>', '')

    def remove_random_bytes(self, html):
        return re.sub('\x14|\x15|\x19|\x1c|\x1d|\xef|\x12|\x13|\xec|\x08|\x01|\x02|\x03|\x04|\x05|\x06|\x07',
                    '', html)

    def ensure_unit(self, raw, unit='px'):
        if re.search(r'\d+$', raw) is not None:
            raw += unit
        return raw

    def upshift_markup(self, root, image_name_map=None):
        self.log.debug('Converting style information to CSS...')
        image_name_map = image_name_map or {}
        size_map = {
            'xx-small': '0.5',
            'x-small': '1',
            'small': '2',
            'medium': '3',
            'large': '4',
            'x-large': '5',
            'xx-large': '6',
            }

        def barename(x):
            return x.rpartition(':')[-1]

        mobi_version = self.book_header.mobi_version
        for x in root.xpath('//ncx'):
            x.getparent().remove(x)
        svg_tags = []
        forwardable_anchors = []
        pagebreak_anchors = []
        BLOCK_TAGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'p'}
        for i, tag in enumerate(root.iter(etree.Element)):
            tag.attrib.pop('xmlns', '')
            for x in tag.attrib:
                if ':' in x:
                    del tag.attrib[x]
            if tag.tag and barename(tag.tag) == 'svg':
                svg_tags.append(tag)
            if tag.tag and barename(tag.tag.lower()) in \
                ('country-region', 'place', 'placetype', 'placename',
                    'state', 'city', 'street', 'address', 'content', 'form'):
                tag.tag = 'div' if tag.tag in ('content', 'form') else 'span'
                for key in tag.attrib.keys():
                    tag.attrib.pop(key)
                continue
            styles, attrib = [], tag.attrib
            if 'style' in attrib:
                style = attrib.pop('style').strip()
                if style:
                    styles.append(style)
            if 'height' in attrib:
                height = attrib.pop('height').strip()
                if (
                        height and '<' not in height and '>' not in height and
                        re.search(r'\d+', height)):
                    if tag.tag in ('table', 'td', 'tr'):
                        pass
                    elif tag.tag == 'img':
                        tag.set('height', height)
                    else:
                        if tag.tag == 'div' and not tag.text and \
                                (not tag.tail or not tag.tail.strip()) and \
                                not len(list(tag.iterdescendants())):
                            # Paragraph spacer
                            # Insert nbsp so that the element is never
                            # discarded by a renderer
                            tag.text = '\u00a0'  # nbsp
                            styles.append('height: %s' %
                                    self.ensure_unit(height))
                        else:
                            styles.append('margin-top: %s' % self.ensure_unit(height))
            if 'width' in attrib:
                width = attrib.pop('width').strip()
                if width and re.search(r'\d+', width):
                    if tag.tag in ('table', 'td', 'tr'):
                        pass
                    elif tag.tag == 'img':
                        tag.set('width', width)
                    else:
                        ewidth = self.ensure_unit(width)
                        styles.append('text-indent: %s' % ewidth)
                        try:
                            ewidth_val = unit_convert(ewidth, 12, 500, 166)
                            self.text_indents[tag] = ewidth_val
                        except:
                            pass
                        if width.startswith('-'):
                            styles.append('margin-left: %s' % self.ensure_unit(width[1:]))
                            try:
                                ewidth_val = unit_convert(ewidth[1:], 12, 500, 166)
                                self.left_margins[tag] = ewidth_val
                            except:
                                pass

            if 'align' in attrib:
                align = attrib.pop('align').strip()
                if align:
                    align = align.lower()
                    if align == 'baseline':
                        styles.append('vertical-align: '+align)
                    else:
                        styles.append('text-align: %s' % align)
            if tag.tag == 'hr':
                if mobi_version == 1:
                    tag.tag = 'div'
                    styles.append('page-break-before: always')
                    styles.append('display: block')
                    styles.append('margin: 0')
            elif tag.tag == 'i':
                tag.tag = 'span'
                tag.attrib['class'] = 'italic'
            elif tag.tag == 'u':
                tag.tag = 'span'
                tag.attrib['class'] = 'underline'
            elif tag.tag == 'b':
                tag.tag = 'span'
                tag.attrib['class'] = 'bold'
            elif tag.tag == 'font':
                sz = tag.get('size', '').lower()
                try:
                    float(sz)
                except ValueError:
                    if sz in list(size_map.keys()):
                        attrib['size'] = size_map[sz]
            elif tag.tag == 'img':
                recindex = None
                for attr in self.IMAGE_ATTRS:
                    recindex = attrib.pop(attr, None) or recindex
                if recindex is not None:
                    try:
                        recindex = int(recindex)
                    except Exception:
                        pass
                    else:
                        attrib['src'] = 'images/' + image_name_map.get(recindex, '%05d.jpg' % recindex)
                for attr in ('width', 'height'):
                    if attr in attrib:
                        val = attrib[attr]
                        if val.lower().endswith('em'):
                            try:
                                nval = float(val[:-2])
                                nval *= 16 * (168.451/72)  # Assume this was set using the Kindle profile
                                attrib[attr] = "%dpx"%int(nval)
                            except:
                                del attrib[attr]
                        elif val.lower().endswith('%'):
                            del attrib[attr]
            elif tag.tag == 'pre':
                if not tag.text:
                    tag.tag = 'div'

            if (attrib.get('class', None) == 'mbp_pagebreak' and tag.tag ==
                    'div' and 'filepos-id' in attrib):
                pagebreak_anchors.append(tag)

            if 'color' in attrib:
                styles.append('color: ' + attrib.pop('color'))
            if 'bgcolor' in attrib:
                styles.append('background-color: ' + attrib.pop('bgcolor'))

            if 'filepos-id' in attrib:
                attrib['id'] = attrib.pop('filepos-id')
                if 'name' in attrib and attrib['name'] != attrib['id']:
                    attrib['name'] = attrib['id']
            if 'filepos' in attrib:
                filepos = attrib.pop('filepos')
                try:
                    attrib['href'] = "#filepos%d" % int(filepos)
                except ValueError:
                    pass
            if (tag.tag == 'a' and attrib.get('id', '').startswith('filepos') and
                    not tag.text and len(tag) == 0 and (tag.tail is None or not
                        tag.tail.strip()) and getattr(tag.getnext(), 'tag',
                            None) in BLOCK_TAGS):
                # This is an empty anchor immediately before a block tag, move
                # the id onto the block tag instead
                forwardable_anchors.append(tag)

            if styles:
                ncls = None
                rule = '; '.join(styles)
                for sel, srule in self.tag_css_rules.items():
                    if srule == rule:
                        ncls = sel
                        break
                if ncls is None:
                    ncls = 'calibre_%d' % i
                    self.tag_css_rules[ncls] = rule
                cls = attrib.get('class', '')
                cls = cls + (' ' if cls else '') + ncls
                attrib['class'] = cls

        for tag in svg_tags:
            images = tag.xpath('descendant::img[@src]')
            parent = tag.getparent()

            if images and hasattr(parent, 'find'):
                index = parent.index(tag)
                for img in images:
                    img.getparent().remove(img)
                    img.tail = img.text = None
                    parent.insert(index, img)

            if hasattr(parent, 'remove'):
                parent.remove(tag)

        for tag in pagebreak_anchors:
            anchor = tag.attrib['id']
            del tag.attrib['id']
            if 'name' in tag.attrib:
                del tag.attrib['name']
            p = tag.getparent()
            a = p.makeelement('a')
            a.attrib['id'] = anchor
            p.insert(p.index(tag)+1, a)
            if getattr(a.getnext(), 'tag', None) in BLOCK_TAGS:
                forwardable_anchors.append(a)

        for tag in forwardable_anchors:
            block = tag.getnext()
            tag.getparent().remove(tag)

            if 'id' in block.attrib:
                tag.tail = block.text
                block.text = None
                block.insert(0, tag)
            else:
                block.attrib['id'] = tag.attrib['id']

        # WebKit fails to navigate to anchors located on <br> tags
        for br in root.xpath('/body/br[@id]'):
            br.tag = 'div'

    def get_left_whitespace(self, tag):

        def whitespace(tag):
            lm = ti = 0.0
            if tag.tag == 'p':
                ti = unit_convert('1.5em', 12, 500, 166)
            if tag.tag == 'blockquote':
                lm = unit_convert('2em', 12, 500, 166)
            lm = self.left_margins.get(tag, lm)
            ti = self.text_indents.get(tag, ti)
            try:
                lm = float(lm)
            except:
                lm = 0.0
            try:
                ti = float(ti)
            except:
                ti = 0.0
            return lm + ti

        parent = tag
        ans = 0.0
        while parent is not None:
            ans += whitespace(parent)
            parent = parent.getparent()

        return ans

    def create_opf(self, htmlfile, guide=None, root=None):
        mi = getattr(self.book_header.exth, 'mi', self.embedded_mi)
        if mi is None:
            mi = MetaInformation(self.book_header.title, [_('Unknown')])
        opf = OPFCreator(os.path.dirname(htmlfile), mi)
        if hasattr(self.book_header.exth, 'cover_offset'):
            opf.cover = 'images/%05d.jpg' % (self.book_header.exth.cover_offset + 1)
        elif mi.cover is not None:
            opf.cover = mi.cover
        else:
            opf.cover = 'images/%05d.jpg' % 1
            if not os.path.exists(os.path.join(os.path.dirname(htmlfile),
                * opf.cover.split('/'))):
                opf.cover = None

        cover = opf.cover
        cover_copied = None
        if cover is not None:
            cover = cover.replace('/', os.sep)
            if os.path.exists(cover):
                ncover = 'images'+os.sep+'calibre_cover.jpg'
                if os.path.exists(ncover):
                    os.remove(ncover)
                shutil.copyfile(cover, ncover)
                cover_copied = os.path.abspath(ncover)
                opf.cover = ncover.replace(os.sep, '/')

        manifest = [(htmlfile, 'application/xhtml+xml'),
            (os.path.abspath('styles.css'), 'text/css')]
        bp = os.path.dirname(htmlfile)
        added = set()
        for i in getattr(self, 'image_names', []):
            path = os.path.join(bp, 'images', i)
            added.add(path)
            manifest.append((path, guess_type(path)[0] or 'image/jpeg'))
        if cover_copied is not None:
            manifest.append((cover_copied, 'image/jpeg'))

        opf.create_manifest(manifest)
        opf.create_spine([os.path.basename(htmlfile)])
        toc = None
        if guide is not None:
            opf.create_guide(guide)
            for ref in opf.guide:
                if ref.type.lower() == 'toc':
                    toc = ref.href()

        ncx_manifest_entry = None
        if toc:
            ncx_manifest_entry = 'toc.ncx'
            elems = root.xpath('//*[@id="%s"]' % toc.partition('#')[-1])
            tocobj = None
            ent_pat = re.compile(r'&(\S+?);')
            if elems:
                tocobj = TOC()
                found = False
                reached = False
                for x in root.iter():
                    if x == elems[-1]:
                        reached = True
                        continue
                    if reached and x.tag == 'a':
                        href = x.get('href', '')
                        if href and re.match(r'\w+://', href) is None:
                            try:
                                text = ' '.join([t.strip() for t in
                                    x.xpath('descendant::text()')])
                            except:
                                text = ''
                            text = ent_pat.sub(entity_to_unicode, text)
                            item = tocobj.add_item(toc.partition('#')[0], href[1:],
                                text)
                            item.left_space = int(self.get_left_whitespace(x))
                            found = True
                    if reached and found and x.get('class', None) == 'mbp_pagebreak':
                        break
            if tocobj is not None:
                tocobj = self.structure_toc(tocobj)
                opf.set_toc(tocobj)

        return opf, ncx_manifest_entry

    def structure_toc(self, toc):
        indent_vals = set()
        for item in toc:
            indent_vals.add(item.left_space)
        if len(indent_vals) > 6 or len(indent_vals) < 2:
            # Too many or too few levels, give up
            return toc
        indent_vals = sorted(indent_vals)

        last_found = [None for i in indent_vals]

        newtoc = TOC()

        def find_parent(level):
            candidates = last_found[:level]
            for x in reversed(candidates):
                if x is not None:
                    return x
            return newtoc

        for item in toc:
            level = indent_vals.index(item.left_space)
            parent = find_parent(level)
            last_found[level] = parent.add_item(item.href, item.fragment,
                        item.text)

        return newtoc

    def sizeof_trailing_entries(self, data):
        def sizeof_trailing_entry(ptr, psize):
            bitpos, result = 0, 0
            while True:
                v = ord(ptr[psize-1:psize])
                result |= (v & 0x7F) << bitpos
                bitpos += 7
                psize -= 1
                if (v & 0x80) != 0 or (bitpos >= 28) or (psize == 0):
                    return result

        num = 0
        size = len(data)
        flags = self.book_header.extra_flags >> 1
        while flags:
            if flags & 1:
                try:
                    num += sizeof_trailing_entry(data, size - num)
                except IndexError:
                    self.warn_about_trailing_entry_corruption()
                    return 0
            flags >>= 1
        if self.book_header.extra_flags & 1:
            off = size - num - 1
            num += (ord(data[off:off+1]) & 0x3) + 1
        return num

    def warn_about_trailing_entry_corruption(self):
        if not self.warned_about_trailing_entry_corruption:
            self.warned_about_trailing_entry_corruption = True
            self.log.warn('The trailing data entries in this MOBI file are corrupted, you might see corrupted text in the output')

    def text_section(self, index):
        data = self.sections[index][0]
        trail_size = self.sizeof_trailing_entries(data)
        return data[:len(data)-trail_size]

    def extract_text(self, offset=1):
        self.log.debug('Extracting text...')
        text_sections = [self.text_section(i) for i in range(offset,
            min(self.book_header.records + offset, len(self.sections)))]
        processed_records = list(range(offset-1, self.book_header.records +
            offset))

        self.mobi_html = b''

        if self.book_header.compression_type == b'DH':
            huffs = [self.sections[i][0] for i in
                range(self.book_header.huff_offset,
                    self.book_header.huff_offset + self.book_header.huff_number)]
            processed_records += list(range(self.book_header.huff_offset,
                self.book_header.huff_offset + self.book_header.huff_number))
            huff = HuffReader(huffs)
            unpack = huff.unpack

        elif self.book_header.compression_type == b'\x00\x02':
            unpack = decompress_doc

        elif self.book_header.compression_type == b'\x00\x01':
            unpack = lambda x: x
        else:
            raise MobiError('Unknown compression algorithm: %r' % self.book_header.compression_type)
        self.mobi_html = b''.join(map(unpack, text_sections))
        if self.mobi_html.endswith(b'#'):
            self.mobi_html = self.mobi_html[:-1]

        if self.book_header.ancient and b'<html' not in self.mobi_html[:300].lower():
            self.mobi_html = self.mobi_html.replace(b'\r ', b'\n\n ')
        self.mobi_html = self.mobi_html.replace(b'\0', b'')
        if self.book_header.codec == 'cp1252':
            self.mobi_html = self.mobi_html.replace(b'\x1e', b'')  # record separator
            self.mobi_html = self.mobi_html.replace(b'\x02', b'')  # start of text
        return processed_records

    def replace_page_breaks(self):
        self.processed_html = self.PAGE_BREAK_PAT.sub(
            r'<div \1 class="mbp_pagebreak" />',
            self.processed_html)

    def add_anchors(self):
        self.log.debug('Adding anchors...')
        positions = set()
        link_pattern = re.compile(br'''<[^<>]+filepos=['"]{0,1}(\d+)[^<>]*>''',
            re.IGNORECASE)
        for match in link_pattern.finditer(self.mobi_html):
            positions.add(int(match.group(1)))
        pos = 0
        processed_html = []
        end_tag_re = re.compile(br'<\s*/')
        for end in sorted(positions):
            if end == 0:
                continue
            oend = end
            l = self.mobi_html.find(b'<', end)
            r = self.mobi_html.find(b'>', end)
            anchor = b'<a id="filepos%d"></a>'
            if r > -1 and (r < l or l == end or l == -1):
                p = self.mobi_html.rfind(b'<', 0, end + 1)
                if (pos < end and p > -1 and not end_tag_re.match(self.mobi_html[p:r]) and
                        not self.mobi_html[p:r + 1].endswith(b'/>')):
                    anchor = b' filepos-id="filepos%d"'
                    end = r
                else:
                    end = r + 1
            processed_html.append(self.mobi_html[pos:end] + (anchor % oend))
            pos = end
        processed_html.append(self.mobi_html[pos:])
        processed_html = b''.join(processed_html)

        # Remove anchors placed inside entities
        self.processed_html = re.sub(br'&([^;]*?)(<a id="filepos\d+"></a>)([^;]*);',
                br'&\1\3;\2', processed_html)

    def extract_images(self, processed_records, output_dir):
        self.log.debug('Extracting images...')
        output_dir = os.path.abspath(os.path.join(output_dir, 'images'))
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        image_index = 0
        self.image_names = []
        image_name_map = {}
        start = getattr(self.book_header, 'first_image_index', -1)
        if start > self.num_sections or start < 0:
            # BAEN PRC files have bad headers
            start = 0
        for i in range(start, self.num_sections):
            if i in processed_records:
                continue
            processed_records.append(i)
            data  = self.sections[i][0]
            image_index += 1
            if data[:4] in {b'FLIS', b'FCIS', b'SRCS', b'\xe9\x8e\r\n',
                    b'RESC', b'BOUN', b'FDST', b'DATP', b'AUDI', b'VIDE'}:
                # This record is a known non image type, no need to try to
                # load the image
                continue

            try:
                imgfmt = what(None, data)
            except Exception:
                continue
            if imgfmt not in {'jpg', 'jpeg', 'gif', 'png', 'bmp'}:
                continue
            if imgfmt == 'jpeg':
                imgfmt = 'jpg'
            if imgfmt == 'gif':
                try:
                    data = gif_data_to_png_data(data)
                    imgfmt = 'png'
                except AnimatedGIF:
                    pass
                except OSError:
                    continue
            path = os.path.join(output_dir, '%05d.%s' % (image_index, imgfmt))
            image_name_map[image_index] = os.path.basename(path)
            if imgfmt == 'png':
                with open(path, 'wb') as f:
                    f.write(data)
            else:
                try:
                    save_cover_data_to(data, path, minify_to=(10000, 10000))
                except Exception:
                    continue
            self.image_names.append(os.path.basename(path))
        return image_name_map


def test_mbp_regex():
    for raw, m in iteritems({
        '<mbp:pagebreak></mbp:pagebreak>':'',
        '<mbp:pagebreak xxx></mbp:pagebreak>yyy':' xxxyyy',
        '<mbp:pagebreak> </mbp:pagebreak>':'',
        '<mbp:pagebreak>xxx':'xxx',
        '<mbp:pagebreak/>xxx':'xxx',
        '<mbp:pagebreak sdf/ >xxx':' sdfxxx',
        '<mbp:pagebreak / >':' ',
        '</mbp:pagebreak>':'',
        '</mbp:pagebreak sdf>':' sdf',
        '</mbp:pagebreak><mbp:pagebreak></mbp:pagebreak>xxx':'xxx',
        }):
        ans = MobiReader.PAGE_BREAK_PAT.sub(r'\1', raw)
        if ans != m:
            raise Exception('%r != %r for %r'%(ans, m, raw))
