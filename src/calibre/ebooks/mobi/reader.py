__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Read data from .mobi files
'''

import shutil, os, re, struct, textwrap, cStringIO, sys

try:
    from PIL import Image as PILImage
    PILImage
except ImportError:
    import Image as PILImage

from lxml import html, etree

from calibre import xml_entity_to_unicode, CurrentDir, entity_to_unicode, \
    replace_entities
from calibre.utils.filenames import ascii_filename
from calibre.utils.date import parse_date
from calibre.ptempfile import TemporaryDirectory
from calibre.ebooks import DRMError
from calibre.ebooks.chardet import ENCODING_PATS
from calibre.ebooks.mobi import MobiError
from calibre.ebooks.mobi.huffcdic import HuffReader
from calibre.ebooks.mobi.langcodes import main_language, sub_language, mobi2iana
from calibre.ebooks.compression.palmdoc import decompress_doc
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata.opf2 import OPFCreator, OPF
from calibre.ebooks.metadata.toc import TOC

class EXTHHeader(object):

    def __init__(self, raw, codec, title):
        self.doctype = raw[:4]
        self.length, self.num_items = struct.unpack('>LL', raw[4:12])
        raw = raw[12:]
        pos = 0
        self.mi = MetaInformation(_('Unknown'), [_('Unknown')])
        self.has_fake_cover = True
        left = self.num_items

        while left > 0:
            left -= 1
            id, size = struct.unpack('>LL', raw[pos:pos + 8])
            content = raw[pos + 8:pos + size]
            pos += size
            if id >= 100 and id < 200:
                self.process_metadata(id, content, codec)
            elif id == 203:
                self.has_fake_cover = bool(struct.unpack('>L', content)[0])
            elif id == 201:
                co, = struct.unpack('>L', content)
                if co < 1e7:
                    self.cover_offset = co
            elif id == 202:
                self.thumbnail_offset, = struct.unpack('>L', content)
            elif id == 501:
                # cdetype
                pass
            elif id == 502:
                # last update time
                pass
            elif id == 503: # Long title
                if not title or title == _('Unknown') or \
                        'USER_CONTENT' in title or title.startswith('dtp_'):
                    try:
                        title = content.decode(codec)
                    except:
                        pass
            #else:
            #    print 'unknown record', id, repr(content)
        if title:
            self.mi.title = replace_entities(title)

    def process_metadata(self, id, content, codec):
        if id == 100:
            if self.mi.authors == [_('Unknown')]:
                self.mi.authors = []
            au = content.decode(codec, 'ignore').strip()
            self.mi.authors.append(au)
            if re.match(r'\S+?\s*,\s+\S+', au.strip()):
                self.mi.author_sort = au.strip()
        elif id == 101:
            self.mi.publisher = content.decode(codec, 'ignore').strip()
        elif id == 103:
            self.mi.comments  = content.decode(codec, 'ignore')
        elif id == 104:
            self.mi.isbn      = content.decode(codec, 'ignore').strip().replace('-', '')
        elif id == 105:
            if not self.mi.tags:
                self.mi.tags = []
            self.mi.tags.extend([x.strip() for x in content.decode(codec,
                'ignore').split(';')])
            self.mi.tags = list(set(self.mi.tags))
        elif id == 106:
            try:
                self.mi.pubdate = parse_date(content, as_utc=False)
            except:
                pass
        elif id == 108:
            pass # Producer
        #else:
        #    print 'unhandled metadata record', id, repr(content)


class BookHeader(object):

    def __init__(self, raw, ident, user_encoding, log, try_extra_data_fix=False):
        self.log = log
        self.compression_type = raw[:2]
        self.records, self.records_size = struct.unpack('>HH', raw[8:12])
        self.encryption_type, = struct.unpack('>H', raw[12:14])
        if ident == 'TEXTREAD':
            self.codepage = 1252
        if len(raw) <= 16:
            self.codec = 'cp1252'
            self.extra_flags = 0
            self.title = _('Unknown')
            self.language = 'ENGLISH'
            self.sublanguage = 'NEUTRAL'
            self.exth_flag, self.exth = 0, None
            self.ancient = True
            self.first_image_index = -1
            self.mobi_version = 1
        else:
            self.ancient = False
            self.doctype = raw[16:20]
            self.length, self.type, self.codepage, self.unique_id, \
                self.version = struct.unpack('>LLLLL', raw[20:40])


            try:
                self.codec = {
                    1252: 'cp1252',
                    65001: 'utf-8',
                    }[self.codepage]
            except (IndexError, KeyError):
                self.codec = 'cp1252' if user_encoding is None else user_encoding
                log.warn('Unknown codepage %d. Assuming %s' % (self.codepage,
                    self.codec))
            if ident == 'TEXTREAD' or self.length < 0xE4 or 0xE8 < self.length \
                or (try_extra_data_fix and self.length == 0xE4):
                self.extra_flags = 0
            else:
                self.extra_flags, = struct.unpack('>H', raw[0xF2:0xF4])

            if self.compression_type == 'DH':
                self.huff_offset, self.huff_number = struct.unpack('>LL', raw[0x70:0x78])

            toff, tlen = struct.unpack('>II', raw[0x54:0x5c])
            tend = toff + tlen
            self.title = raw[toff:tend] if tend < len(raw) else _('Unknown')
            langcode  = struct.unpack('!L', raw[0x5C:0x60])[0]
            langid    = langcode & 0xFF
            sublangid = (langcode >> 10) & 0xFF
            self.language = main_language.get(langid, 'ENGLISH')
            self.sublanguage = sub_language.get(sublangid, 'NEUTRAL')
            self.mobi_version = struct.unpack('>I', raw[0x68:0x6c])[0]
            self.first_image_index = struct.unpack('>L', raw[0x6c:0x6c + 4])[0]

            self.exth_flag, = struct.unpack('>L', raw[0x80:0x84])
            self.exth = None
            if not isinstance(self.title, unicode):
                self.title = self.title.decode(self.codec, 'replace')
            if self.exth_flag & 0x40:
                try:
                    self.exth = EXTHHeader(raw[16 + self.length:], self.codec, self.title)
                    self.exth.mi.uid = self.unique_id
                    try:
                        self.exth.mi.language = mobi2iana(langid, sublangid)
                    except:
                        self.log.exception('Unknown language code')
                except:
                    self.log.exception('Invalid EXTH header')
                    self.exth_flag = 0


class MetadataHeader(BookHeader):
    def __init__(self, stream, log):
        self.stream = stream
        self.ident = self.identity()
        self.num_sections = self.section_count()
        if self.num_sections >= 2:
            header = self.header()
            BookHeader.__init__(self, header, self.ident, None, log)
        else:
            self.exth = None

    def identity(self):
        self.stream.seek(60)
        ident = self.stream.read(8).upper()
        if ident not in ['BOOKMOBI', 'TEXTREAD']:
            raise MobiError('Unknown book type: %s' % ident)
        return ident

    def section_count(self):
        self.stream.seek(76)
        return struct.unpack('>H', self.stream.read(2))[0]

    def section_offset(self, number):
        self.stream.seek(78 + number * 8)
        return struct.unpack('>LBBBB', self.stream.read(8))[0]

    def header(self):
        section_headers = []
        # First section with the metadata
        section_headers.append(self.section_offset(0))
        # Second section used to get the lengh of the first
        section_headers.append(self.section_offset(1))

        end_off = section_headers[1]
        off = section_headers[0]
        self.stream.seek(off)
        return self.stream.read(end_off - off)

    def section_data(self, number):
        start = self.section_offset(number)
        if number == self.num_sections -1:
            end = os.stat(self.stream.name).st_size
        else:
            end = self.section_offset(number + 1)
        self.stream.seek(start)
        try:
            return self.stream.read(end - start)
        except OverflowError:
            return self.stream.read(os.stat(self.stream.name).st_size - start)


class MobiReader(object):
    PAGE_BREAK_PAT = re.compile(r'(<[/]{0,1}mbp:pagebreak\s*[/]{0,1}>)+', re.IGNORECASE)
    IMAGE_ATTRS = ('lowrecindex', 'recindex', 'hirecindex')

    def __init__(self, filename_or_stream, log, user_encoding=None, debug=None,
            try_extra_data_fix=False):
        self.log = log
        self.debug = debug
        self.embedded_mi = None
        self.base_css_rules = textwrap.dedent('''
                blockquote { margin: 0em 0em 0em 2em; text-align: justify }

                p { margin: 0em; text-align: justify }

                .bold { font-weight: bold }

                .italic { font-style: italic }

                .mbp_pagebreak {
                    page-break-after: always; margin: 0; display: block
                }
                ''')
        self.tag_css_rules = {}

        if hasattr(filename_or_stream, 'read'):
            stream = filename_or_stream
            stream.seek(0)
        else:
            stream = open(filename_or_stream, 'rb')

        raw = stream.read()
        if raw.startswith('TPZ'):
            raise ValueError(_('This is an Amazon Topaz book. It cannot be processed.'))

        self.header   = raw[0:72]
        self.name     = self.header[:32].replace('\x00', '')
        self.num_sections, = struct.unpack('>H', raw[76:78])

        self.ident = self.header[0x3C:0x3C + 8].upper()
        if self.ident not in ['BOOKMOBI', 'TEXTREAD']:
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


        self.book_header = BookHeader(self.sections[0][0], self.ident,
            user_encoding, self.log, try_extra_data_fix=try_extra_data_fix)
        self.name = self.name.decode(self.book_header.codec, 'replace')

    def extract_content(self, output_dir, parse_cache):
        output_dir = os.path.abspath(output_dir)
        if self.book_header.encryption_type != 0:
            raise DRMError(self.name)

        processed_records = self.extract_text()
        if self.debug is not None:
            parse_cache['calibre_raw_mobi_markup'] = self.mobi_html
        self.add_anchors()
        self.processed_html = self.processed_html.decode(self.book_header.codec,
            'ignore')
        self.processed_html = self.processed_html.replace('</</', '</')
        self.processed_html = re.sub(r'</([a-zA-Z]+)<', r'</\1><',
                self.processed_html)

        for pat in ENCODING_PATS:
            self.processed_html = pat.sub('', self.processed_html)
        self.processed_html = re.sub(r'&(\S+?);', xml_entity_to_unicode,
            self.processed_html)
        self.extract_images(processed_records, output_dir)
        self.replace_page_breaks()
        self.cleanup_html()

        self.log.debug('Parsing HTML...')
        try:
            root = html.fromstring(self.processed_html)
            if len(root.xpath('//html')) > 5:
                root = html.fromstring(self.processed_html.replace('\x0c',
                    '').replace('\x14', ''))
        except:
            self.log.warning('MOBI markup appears to contain random bytes. Stripping.')
            self.processed_html = self.remove_random_bytes(self.processed_html)
            root = html.fromstring(self.processed_html)
        if root.xpath('descendant::p/descendant::p'):
            from lxml.html import soupparser
            self.log.warning('Malformed markup, parsing using BeautifulSoup')
            try:
                root = soupparser.fromstring(self.processed_html)
            except Exception:
                self.log.warning('MOBI markup appears to contain random bytes. Stripping.')
                self.processed_html = self.remove_random_bytes(self.processed_html)
                root = soupparser.fromstring(self.processed_html)


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
            for x in root: root.remove(x)
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
            title.text = self.book_header.title
            title.tail = '\n\t'
            head.insert(0, title)
            head.text = '\n\t'

        self.upshift_markup(root)
        guides = root.xpath('//guide')
        guide = guides[0] if guides else None
        metadata_elems = root.xpath('//metadata')
        if metadata_elems and self.book_header.exth is None:
            self.read_embedded_metadata(root, metadata_elems[0], guide)
        for elem in guides + metadata_elems:
            elem.getparent().remove(elem)
        fname = self.name.encode('ascii', 'replace')
        fname = re.sub(r'[\x08\x15\0]+', '', fname)
        if not fname:
            fname = 'dummy'
        htmlfile = os.path.join(output_dir,
            ascii_filename(fname) + '.html')
        try:
            for ref in guide.xpath('descendant::reference'):
                if ref.attrib.has_key('href'):
                    ref.attrib['href'] = os.path.basename(htmlfile) + ref.attrib['href']
        except AttributeError:
            pass
        parse_cache[htmlfile] = root
        self.htmlfile = htmlfile
        ncx = cStringIO.StringIO()
        opf, ncx_manifest_entry = self.create_opf(htmlfile, guide, root)
        self.created_opf_path = os.path.splitext(htmlfile)[0] + '.opf'
        opf.render(open(self.created_opf_path, 'wb'), ncx,
            ncx_manifest_entry=ncx_manifest_entry)
        ncx = ncx.getvalue()
        if ncx:
            ncx_path = os.path.join(os.path.dirname(htmlfile), 'toc.ncx')
            open(ncx_path, 'wb').write(ncx)

        with open('styles.css', 'wb') as s:
            s.write(self.base_css_rules + '\n\n')
            for cls, rule in self.tag_css_rules.items():
                if isinstance(rule, unicode):
                    rule = rule.encode('utf-8')
                s.write('.%s { %s }\n\n' % (cls, rule))


        if self.book_header.exth is not None or self.embedded_mi is not None:
            self.log.debug('Creating OPF...')
            ncx = cStringIO.StringIO()
            opf, ncx_manifest_entry  = self.create_opf(htmlfile, guide, root)
            opf.render(open(os.path.splitext(htmlfile)[0] + '.opf', 'wb'), ncx,
                ncx_manifest_entry)
            ncx = ncx.getvalue()
            if ncx:
                open(os.path.splitext(htmlfile)[0] + '.ncx', 'wb').write(ncx)

    def read_embedded_metadata(self, root, elem, guide):
        raw = '<?xml version="1.0" encoding="utf-8" ?>\n<package>' + \
                html.tostring(elem, encoding='utf-8') + '</package>'
        stream = cStringIO.StringIO(raw)
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
        if self.book_header.ancient and '<html' not in self.mobi_html[:300].lower():
            self.processed_html = '<html><p>' + self.processed_html.replace('\n\n', '<p>') + '</html>'
        self.processed_html = self.processed_html.replace('\r\n', '\n')
        self.processed_html = self.processed_html.replace('> <', '>\n<')
        self.processed_html = self.processed_html.replace('<mbp: ', '<mbp:')
        self.processed_html = re.sub(r'<?xml[^>]*>', '', self.processed_html)
        # Rearrange various style tags & paragraph tags so that lxml and BeautifulSoup don't get upset
        self.processed_html = re.sub(r'(?i)(?P<styletags>(<(h\d+|i|b|u|em|small|big|strong|tt)>\s*){1,})(?P<para><p[^>]*>)', '\g<para>'+'\g<styletags>', self.processed_html)
        self.processed_html = re.sub(r'(?i)(?P<para></p[^>]*>)\s*(?P<styletags>(</(h\d+|i|b|u|em|small|big|strong|tt)>\s*){1,})', '\g<styletags>'+'\g<para>', self.processed_html)

    def remove_random_bytes(self, html):
        return re.sub('\x14|\x15|\x19|\x1c|\x1d|\xef|\x12|\x13|\xec|\x08',
                    '', html)

    def ensure_unit(self, raw, unit='px'):
        if re.search(r'\d+$', raw) is not None:
            raw += unit
        return raw

    def upshift_markup(self, root):
        self.log.debug('Converting style information to CSS...')
        size_map = {
            'xx-small': '0.5',
            'x-small': '1',
            'small': '2',
            'medium': '3',
            'large': '4',
            'x-large': '5',
            'xx-large': '6',
            }
        mobi_version = self.book_header.mobi_version
        for x in root.xpath('//ncx'):
            x.getparent().remove(x)
        for i, tag in enumerate(root.iter(etree.Element)):
            tag.attrib.pop('xmlns', '')
            for x in tag.attrib:
                if ':' in x:
                    del tag.attrib[x]
            if tag.tag in ('country-region', 'place', 'placetype', 'placename',
                'state', 'city', 'street', 'address', 'content', 'form'):
                tag.tag = 'div' if tag.tag in ('content', 'form') else 'span'
                for key in tag.attrib.keys():
                    tag.attrib.pop(key)
                continue
            styles, attrib = [], tag.attrib
            if attrib.has_key('style'):
                style = attrib.pop('style').strip()
                if style:
                    styles.append(style)
            if attrib.has_key('height'):
                height = attrib.pop('height').strip()
                if height and '<' not in height and '>' not in height and \
                    re.search(r'\d+', height):
                        if tag.tag in ('table', 'td', 'tr'):
                            pass
                        elif tag.tag == 'img':
                            tag.set('height', height)
                        else:
                            styles.append('margin-top: %s' % self.ensure_unit(height))
            if attrib.has_key('width'):
                width = attrib.pop('width').strip()
                if width and re.search(r'\d+', width):
                    if tag.tag in ('table', 'td', 'tr'):
                        pass
                    elif tag.tag == 'img':
                        tag.set('width', width)
                    else:
                        styles.append('text-indent: %s' % self.ensure_unit(width))
                        if width.startswith('-'):
                            styles.append('margin-left: %s' % self.ensure_unit(width[1:]))
            if attrib.has_key('align'):
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
            elif tag.tag == 'b':
                tag.tag = 'span'
                tag.attrib['class'] = 'bold'
            elif tag.tag == 'font':
                sz = tag.get('size', '').lower()
                try:
                    float(sz)
                except ValueError:
                    if sz in size_map.keys():
                        attrib['size'] = size_map[sz]
            elif tag.tag == 'img':
                recindex = None
                for attr in self.IMAGE_ATTRS:
                    recindex = attrib.pop(attr, None) or recindex
                if recindex is not None:
                    try:
                        recindex = '%05d'%int(recindex)
                    except:
                        pass
                    attrib['src'] = 'images/%s.jpg' % recindex
                for attr in ('width', 'height'):
                    if attr in attrib:
                        val = attrib[attr]
                        if val.lower().endswith('em'):
                            try:
                                nval = float(val[:-2])
                                nval *= 16 * (168.451/72) # Assume this was set using the Kindle profile
                                attrib[attr] = "%dpx"%int(nval)
                            except:
                                del attrib[attr]
                        elif val.lower().endswith('%'):
                            del attrib[attr]
            elif tag.tag == 'pre':
                if not tag.text:
                    tag.tag = 'div'

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
        added = set([])
        for i in getattr(self, 'image_names', []):
            path = os.path.join(bp, 'images', i)
            added.add(path)
            manifest.append((path, 'image/jpeg'))
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
                reached = False
                for x in root.iter():
                    if x == elems[-1]:
                        reached = True
                        continue
                    if reached and x.tag == 'a':
                        href = x.get('href', '')
                        if href and re.match('\w+://', href) is None:
                            try:
                                text = u' '.join([t.strip() for t in \
                                    x.xpath('descendant::text()')])
                            except:
                                text = ''
                            text = ent_pat.sub(entity_to_unicode, text)
                            tocobj.add_item(toc.partition('#')[0], href[1:],
                                text)
                    if reached and x.get('class', None) == 'mbp_pagebreak':
                        break
            if tocobj is not None:
                opf.set_toc(tocobj)

        return opf, ncx_manifest_entry


    def sizeof_trailing_entries(self, data):
        def sizeof_trailing_entry(ptr, psize):
            bitpos, result = 0, 0
            while True:
                v = ord(ptr[psize-1])
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
                num += sizeof_trailing_entry(data, size - num)
            flags >>= 1
        if self.book_header.extra_flags & 1:
            num += (ord(data[size - num - 1]) & 0x3) + 1
        return num

    def text_section(self, index):
        data = self.sections[index][0]
        trail_size = self.sizeof_trailing_entries(data)
        return data[:len(data)-trail_size]

    def extract_text(self):
        self.log.debug('Extracting text...')
        text_sections = [self.text_section(i) for i in range(1, self.book_header.records + 1)]
        processed_records = list(range(0, self.book_header.records + 1))

        self.mobi_html = ''

        if self.book_header.compression_type == 'DH':
            huffs = [self.sections[i][0] for i in
                range(self.book_header.huff_offset,
                    self.book_header.huff_offset + self.book_header.huff_number)]
            processed_records += list(range(self.book_header.huff_offset,
                self.book_header.huff_offset + self.book_header.huff_number))
            huff = HuffReader(huffs)
            self.mobi_html = huff.decompress(text_sections)

        elif self.book_header.compression_type == '\x00\x02':
            for section in text_sections:
                self.mobi_html += decompress_doc(section)

        elif self.book_header.compression_type == '\x00\x01':
            self.mobi_html = ''.join(text_sections)
        else:
            raise MobiError('Unknown compression algorithm: %s' % repr(self.book_header.compression_type))
        if self.book_header.ancient and '<html' not in self.mobi_html[:300].lower():
            self.mobi_html = self.mobi_html.replace('\r ', '\n\n ')
        self.mobi_html = self.mobi_html.replace('\0', '')
        if self.book_header.codec == 'cp1252':
            self.mobi_html = self.mobi_html.replace('\x1e', '') # record separator
            self.mobi_html = self.mobi_html.replace('\x02', '') # start of text
        return processed_records


    def replace_page_breaks(self):
        self.processed_html = self.PAGE_BREAK_PAT.sub(
            '<div class="mbp_pagebreak" />',
            self.processed_html)

    def add_anchors(self):
        self.log.debug('Adding anchors...')
        positions = set([])
        link_pattern = re.compile(r'''<[^<>]+filepos=['"]{0,1}(\d+)[^<>]*>''',
            re.IGNORECASE)
        for match in link_pattern.finditer(self.mobi_html):
            positions.add(int(match.group(1)))
        pos = 0
        self.processed_html = ''
        end_tag_re = re.compile(r'<\s*/')
        for end in sorted(positions):
            if end == 0:
                continue
            oend = end
            l = self.mobi_html.find('<', end)
            r = self.mobi_html.find('>', end)
            anchor = '<a id="filepos%d"></a>'
            if r > -1 and (r < l or l == end or l == -1):
                p = self.mobi_html.rfind('<', 0, end + 1)
                if pos < end and p > -1 and \
                    not end_tag_re.match(self.mobi_html[p:r]) and \
                    not self.mobi_html[p:r + 1].endswith('/>'):
                        anchor = ' filepos-id="filepos%d"'
                        end = r
                else:
                    end = r + 1
            self.processed_html += self.mobi_html[pos:end] + (anchor % oend)
            pos = end
        self.processed_html += self.mobi_html[pos:]
        # Remove anchors placed inside entities
        self.processed_html = re.sub(r'&([^;]*?)(<a id="filepos\d+"></a>)([^;]*);',
                r'&\1\3;\2', self.processed_html)


    def extract_images(self, processed_records, output_dir):
        self.log.debug('Extracting images...')
        output_dir = os.path.abspath(os.path.join(output_dir, 'images'))
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        image_index = 0
        self.image_names = []
        start = getattr(self.book_header, 'first_image_index', -1)
        if start > self.num_sections or start < 0:
            # BAEN PRC files have bad headers
            start = 0
        for i in range(start, self.num_sections):
            if i in processed_records:
                continue
            processed_records.append(i)
            data  = self.sections[i][0]
            buf = cStringIO.StringIO(data)
            image_index += 1
            try:
                im = PILImage.open(buf)
                im = im.convert('RGB')
            except IOError:
                continue

            path = os.path.join(output_dir, '%05d.jpg' % image_index)
            self.image_names.append(os.path.basename(path))
            im.save(open(path, 'wb'), format='JPEG')

def get_metadata(stream):
    from calibre.utils.logging import Log
    log = Log()
    mi = MetaInformation(os.path.basename(stream.name), [_('Unknown')])
    mh = MetadataHeader(stream, log)
    if mh.title and mh.title != _('Unknown'):
        mi.title = mh.title

    if mh.exth is not None:
        if mh.exth.mi is not None:
            mi = mh.exth.mi
    else:
        size = sys.maxint
        if hasattr(stream, 'seek') and hasattr(stream, 'tell'):
            pos = stream.tell()
            stream.seek(0, 2)
            size = stream.tell()
            stream.seek(pos)
        if size < 4*1024*1024:
            with TemporaryDirectory('_mobi_meta_reader') as tdir:
                with CurrentDir(tdir):
                    mr = MobiReader(stream, log)
                    parse_cache = {}
                    mr.extract_content(tdir, parse_cache)
                    if mr.embedded_mi is not None:
                        mi = mr.embedded_mi
    if hasattr(mh.exth, 'cover_offset'):
        cover_index = mh.first_image_index + mh.exth.cover_offset
        data  = mh.section_data(int(cover_index))
    else:
        data  = mh.section_data(mh.first_image_index)
    buf = cStringIO.StringIO(data)
    try:
        im = PILImage.open(buf)
    except:
        log.exception('Failed to read MOBI cover')
    else:
        obuf = cStringIO.StringIO()
        im.convert('RGB').save(obuf, format='JPEG')
        mi.cover_data = ('jpg', obuf.getvalue())
    return mi
