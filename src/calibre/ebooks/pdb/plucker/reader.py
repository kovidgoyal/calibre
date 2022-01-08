__license__   = 'GPL v3'
__copyright__ = '20011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os
import struct
import zlib

from collections import OrderedDict

from calibre import CurrentDir
from calibre.ebooks.pdb.formatreader import FormatReader
from calibre.ebooks.compression.palmdoc import decompress_doc
from calibre.utils.imghdr import identify
from calibre.utils.img import save_cover_data_to, Canvas, image_from_data
from polyglot.builtins import codepoint_to_chr

DATATYPE_PHTML = 0
DATATYPE_PHTML_COMPRESSED = 1
DATATYPE_TBMP = 2
DATATYPE_TBMP_COMPRESSED = 3
DATATYPE_MAILTO = 4
DATATYPE_LINK_INDEX = 5
DATATYPE_LINKS = 6
DATATYPE_LINKS_COMPRESSED = 7
DATATYPE_BOOKMARKS = 8
DATATYPE_CATEGORY = 9
DATATYPE_METADATA = 10
DATATYPE_STYLE_SHEET = 11
DATATYPE_FONT_PAGE = 12
DATATYPE_TABLE = 13
DATATYPE_TABLE_COMPRESSED = 14
DATATYPE_COMPOSITE_IMAGE = 15
DATATYPE_PAGELIST_METADATA = 16
DATATYPE_SORTED_URL_INDEX = 17
DATATYPE_SORTED_URL = 18
DATATYPE_SORTED_URL_COMPRESSED = 19
DATATYPE_EXT_ANCHOR_INDEX = 20
DATATYPE_EXT_ANCHOR = 21
DATATYPE_EXT_ANCHOR_COMPRESSED = 22

# IETF IANA MIBenum value for the character set.
# See the http://www.iana.org/assignments/character-sets for valid values.
# Not all character sets are handled by Python. This is a small subset that
# the MIBenum maps to Python standard encodings
# from http://docs.python.org/library/codecs.html#standard-encodings
MIBNUM_TO_NAME = {
    3: 'ascii',
    4: 'latin_1',
    5: 'iso8859_2',
    6: 'iso8859_3',
    7: 'iso8859_4',
    8: 'iso8859_5',
    9: 'iso8859_6',
    10: 'iso8859_7',
    11: 'iso8859_8',
    12: 'iso8859_9',
    13: 'iso8859_10',
    17: 'shift_jis',
    18: 'euc_jp',
    27: 'utf_7',
    36: 'euc_kr',
    37: 'iso2022_kr',
    38: 'euc_kr',
    39: 'iso2022_jp',
    40: 'iso2022_jp_2',
    106: 'utf-8',
    109: 'iso8859_13',
    110: 'iso8859_14',
    111: 'iso8859_15',
    112: 'iso8859_16',
    1013: 'utf_16_be',
    1014: 'utf_16_le',
    1015: 'utf_16',
    2009: 'cp850',
    2010: 'cp852',
    2011: 'cp437',
    2013: 'cp862',
    2025: 'gb2312',
    2026: 'big5',
    2028: 'cp037',
    2043: 'cp424',
    2044: 'cp500',
    2046: 'cp855',
    2047: 'cp857',
    2048: 'cp860',
    2049: 'cp861',
    2050: 'cp863',
    2051: 'cp864',
    2052: 'cp865',
    2054: 'cp869',
    2063: 'cp1026',
    2085: 'hz',
    2086: 'cp866',
    2087: 'cp775',
    2089: 'cp858',
    2091: 'cp1140',
    2102: 'big5hkscs',
    2250: 'cp1250',
    2251: 'cp1251',
    2252: 'cp1252',
    2253: 'cp1253',
    2254: 'cp1254',
    2255: 'cp1255',
    2256: 'cp1256',
    2257: 'cp1257',
    2258: 'cp1258',
}


class HeaderRecord:
    '''
    Plucker header. PDB record 0.
    '''

    def __init__(self, raw):
        self.uid, = struct.unpack('>H', raw[0:2])
        # This is labeled version in the spec.
        # 2 is ZLIB compressed,
        # 1 is DOC compressed
        self.compression, = struct.unpack('>H', raw[2:4])
        self.records, = struct.unpack('>H', raw[4:6])
        # uid of the first html file. This should link
        # to other files which in turn may link to others.
        self.home_html = None

        self.reserved = {}
        for i in range(self.records):
            adv = 4*i
            name, = struct.unpack('>H', raw[6+adv:8+adv])
            id, = struct.unpack('>H', raw[8+adv:10+adv])
            self.reserved[id] = name
            if name == 0:
                self.home_html = id


class SectionHeader:
    '''
    Every sections (record) has this header. It gives
    details about the section such as it's uid.
    '''

    def __init__(self, raw):
        self.uid, = struct.unpack('>H', raw[0:2])
        self.paragraphs, = struct.unpack('>H', raw[2:4])
        self.size, = struct.unpack('>H', raw[4:6])
        self.type, = struct.unpack('>B', raw[6:7])
        self.flags, = struct.unpack('>B', raw[7:8])


class SectionHeaderText:
    '''
    Sub header for text records.
    '''

    def __init__(self, section_header, raw):
        # The uncompressed size of each paragraph.
        self.sizes = []
        # uncompressed offset of each paragraph starting
        # at the beginning of the PHTML.
        self.paragraph_offsets = []
        # Paragraph attributes.
        self.attributes = []

        for i in range(section_header.paragraphs):
            adv = 4*i
            self.sizes.append(struct.unpack('>H', raw[adv:2+adv])[0])
            self.attributes.append(struct.unpack('>H', raw[2+adv:4+adv])[0])

        running_offset = 0
        for size in self.sizes:
            running_offset += size
            self.paragraph_offsets.append(running_offset)


class SectionMetadata:
    '''
    Metadata.

    This does not store metadata such as title, or author.
    That metadata would be best retrieved with the PDB (plucker)
    metadata reader.

    This stores document specific information such as the
    text encoding.

    Note: There is a default encoding but each text section
    can be assigned a different encoding.
    '''

    def __init__(self, raw):
        self.default_encoding = 'latin-1'
        self.exceptional_uid_encodings = {}
        self.owner_id = None

        record_count, = struct.unpack('>H', raw[0:2])

        adv = 0
        for i in range(record_count):
            try:
                type, length = struct.unpack_from('>HH', raw, 2 + adv)
            except struct.error:
                break

            # CharSet
            if type == 1:
                val, = struct.unpack('>H', raw[6+adv:8+adv])
                self.default_encoding = MIBNUM_TO_NAME.get(val, 'latin-1')
            # ExceptionalCharSets
            elif type == 2:
                ii_adv = 0
                for ii in range(length // 2):
                    uid, = struct.unpack('>H', raw[6+adv+ii_adv:8+adv+ii_adv])
                    mib, = struct.unpack('>H', raw[8+adv+ii_adv:10+adv+ii_adv])
                    self.exceptional_uid_encodings[uid] = MIBNUM_TO_NAME.get(mib, 'latin-1')
                    ii_adv += 4
            # OwnerID
            elif type == 3:
                self.owner_id = struct.unpack('>I', raw[6+adv:10+adv])
            # Author, Title, PubDate
            # Ignored here. The metadata reader plugin
            # will get this info because if it's missing
            # the metadata reader plugin will use fall
            # back data from elsewhere in the file.
            elif type in (4, 5, 6):
                pass
            # Linked Documents
            elif type == 7:
                pass

            adv += 2*length


class SectionText:
    '''
    Text data. Stores a text section header and the PHTML.
    '''

    def __init__(self, section_header, raw):
        self.header = SectionHeaderText(section_header, raw)
        self.data = raw[section_header.paragraphs * 4:]


class SectionCompositeImage:
    '''
    A composite image consists of a 2D array
    of rows and columns. The entries in the array
    are uid's.
    '''

    def __init__(self, raw):
        self.columns, = struct.unpack('>H', raw[0:2])
        self.rows, = struct.unpack('>H', raw[2:4])

        # [
        #  [uid, uid, uid, ...],
        #  [uid, uid, uid, ...],
        #  ...
        # ]
        #
        # Each item in the layout is in it's
        # correct position in the final
        # composite.
        #
        # Each item in the layout is a uid
        # to an image record.
        self.layout = []
        offset = 4
        for i in range(self.rows):
            col = []
            for j in range(self.columns):
                col.append(struct.unpack('>H', raw[offset:offset+2])[0])
                offset += 2
            self.layout.append(col)


class Reader(FormatReader):
    '''
    Convert a plucker archive into HTML.

    TODO:
          * UTF 16 and 32 characters.
          * Margins.
          * Alignment.
          * Font color.
          * DATATYPE_MAILTO
          * DATATYPE_TABLE(_COMPRESSED)
          * DATATYPE_EXT_ANCHOR_INDEX
          * DATATYPE_EXT_ANCHOR(_COMPRESSED)
    '''

    def __init__(self, header, stream, log, options):
        self.stream = stream
        self.log = log
        self.options = options

        # Mapping of section uid to our internal
        # list of sections.
        self.uid_section_number = OrderedDict()
        self.uid_text_secion_number = OrderedDict()
        self.uid_text_secion_encoding = {}
        self.uid_image_section_number = {}
        self.uid_composite_image_section_number = {}
        self.metadata_section_number = None
        self.default_encoding = 'latin-1'
        self.owner_id = None
        self.sections = []

        # The Plucker record0 header
        self.header_record = HeaderRecord(header.section_data(0))

        for i in range(1, header.num_sections):
            section_number = len(self.sections)
            # The length of the section header.
            # Where the actual data in the section starts.
            start = 8
            section = None

            raw_data = header.section_data(i)
            # Every sections has a section header.
            section_header = SectionHeader(raw_data)

            # Store sections we care able.
            if section_header.type in (DATATYPE_PHTML, DATATYPE_PHTML_COMPRESSED):
                self.uid_text_secion_number[section_header.uid] = section_number
                section = SectionText(section_header, raw_data[start:])
            elif section_header.type in (DATATYPE_TBMP, DATATYPE_TBMP_COMPRESSED):
                self.uid_image_section_number[section_header.uid] = section_number
                section = raw_data[start:]
            elif section_header.type == DATATYPE_METADATA:
                self.metadata_section_number = section_number
                section = SectionMetadata(raw_data[start:])
            elif section_header.type == DATATYPE_COMPOSITE_IMAGE:
                self.uid_composite_image_section_number[section_header.uid] = section_number
                section = SectionCompositeImage(raw_data[start:])

            # Store the section.
            if section:
                self.uid_section_number[section_header.uid] = section_number
                self.sections.append((section_header, section))

        # Store useful information from the metadata section locally
        # to make access easier.
        if self.metadata_section_number:
            mdata_section = self.sections[self.metadata_section_number][1]
            for k, v in mdata_section.exceptional_uid_encodings.items():
                self.uid_text_secion_encoding[k] = v
            self.default_encoding = mdata_section.default_encoding
            self.owner_id = mdata_section.owner_id

        # Get the metadata (tile, author, ...) with the metadata reader.
        from calibre.ebooks.metadata.pdb import get_metadata
        self.mi = get_metadata(stream, False)

    def extract_content(self, output_dir):
        # Each text record is independent (unless the continuation
        # value is set in the previous record). Put each converted
        # text recorded into a separate file. We will reference the
        # home.html file as the first file and let the HTML input
        # plugin assemble the order based on hyperlinks.
        with CurrentDir(output_dir):
            for uid, num in self.uid_text_secion_number.items():
                self.log.debug(f'Writing record with uid: {uid} as {uid}.html')
                with open('%s.html' % uid, 'wb') as htmlf:
                    html = '<html><body>'
                    section_header, section_data = self.sections[num]
                    if section_header.type == DATATYPE_PHTML:
                        html += self.process_phtml(section_data.data, section_data.header.paragraph_offsets)
                    elif section_header.type == DATATYPE_PHTML_COMPRESSED:
                        d = self.decompress_phtml(section_data.data)
                        html += self.process_phtml(d, section_data.header.paragraph_offsets)
                    html += '</body></html>'
                    htmlf.write(html.encode('utf-8'))

        # Images.
        # Cache the image sizes in case they are used by a composite image.
        images = set()
        if not os.path.exists(os.path.join(output_dir, 'images/')):
            os.makedirs(os.path.join(output_dir, 'images/'))
        with CurrentDir(os.path.join(output_dir, 'images/')):
            # Single images.
            for uid, num in self.uid_image_section_number.items():
                section_header, section_data = self.sections[num]
                if section_data:
                    idata = None
                    if section_header.type == DATATYPE_TBMP:
                        idata = section_data
                    elif section_header.type == DATATYPE_TBMP_COMPRESSED:
                        if self.header_record.compression == 1:
                            idata = decompress_doc(section_data)
                        elif self.header_record.compression == 2:
                            idata = zlib.decompress(section_data)
                    try:
                        save_cover_data_to(idata, '%s.jpg' % uid, compression_quality=70)
                        images.add(uid)
                        self.log.debug(f'Wrote image with uid {uid} to images/{uid}.jpg')
                    except Exception as e:
                        self.log.error(f'Failed to write image with uid {uid}: {e}')
                else:
                    self.log.error('Failed to write image with uid %s: No data.' % uid)
            # Composite images.
            # We're going to use the already compressed .jpg images here.
            for uid, num in self.uid_composite_image_section_number.items():
                try:
                    section_header, section_data = self.sections[num]
                    # Get the final width and height.
                    width = 0
                    height = 0
                    for row in section_data.layout:
                        row_width = 0
                        col_height = 0
                        for col in row:
                            if col not in images:
                                raise Exception('Image with uid: %s missing.' % col)
                            w, h = identify(lopen('%s.jpg' % col, 'rb'))[1:]
                            row_width += w
                            if col_height < h:
                                col_height = h
                        if width < row_width:
                            width = row_width
                        height += col_height
                    # Create a new image the total size of all image
                    # parts. Put the parts into the new image.
                    with Canvas(width, height) as canvas:
                        y_off = 0
                        for row in section_data.layout:
                            x_off = 0
                            largest_height = 0
                            for col in row:
                                im = image_from_data(lopen('%s.jpg' % col, 'rb').read())
                                canvas.compose(im, x_off, y_off)
                                w, h = im.width(), im.height()
                                x_off += w
                                if largest_height < h:
                                    largest_height = h
                            y_off += largest_height
                    with lopen('%s.jpg' % uid) as out:
                        out.write(canvas.export(compression_quality=70))
                    self.log.debug(f'Wrote composite image with uid {uid} to images/{uid}.jpg')
                except Exception as e:
                    self.log.error(f'Failed to write composite image with uid {uid}: {e}')

        # Run the HTML through the html processing plugin.
        from calibre.customize.ui import plugin_for_input_format
        html_input = plugin_for_input_format('html')
        for opt in html_input.options:
            setattr(self.options, opt.option.name, opt.recommended_value)
        self.options.input_encoding = 'utf-8'
        odi = self.options.debug_pipeline
        self.options.debug_pipeline = None
        # Determine the home.html record uid. This should be set in the
        # reserved values in the metadata recorded. home.html is the first
        # text record (should have hyper link references to other records)
        # in the document.
        try:
            home_html = self.header_record.home_html
            if not home_html:
                home_html = self.uid_text_secion_number.items()[0][0]
        except:
            raise Exception('Could not determine home.html')
        # Generate oeb from html conversion.
        oeb = html_input.convert(open('%s.html' % home_html, 'rb'), self.options, 'html', self.log, {})
        self.options.debug_pipeline = odi

        return oeb

    def decompress_phtml(self, data):
        if self.header_record.compression == 2:
            if self.owner_id:
                raise NotImplementedError
            return zlib.decompress(data)
        elif self.header_record.compression == 1:
            from calibre.ebooks.compression.palmdoc import decompress_doc
            return decompress_doc(data)

    def process_phtml(self, d, paragraph_offsets=()):
        html = '<p id="p0">'
        offset = 0
        paragraph_open = True
        link_open = False
        need_set_p_id = False
        p_num = 1
        font_specifier_close = ''

        while offset < len(d):
            if not paragraph_open:
                if need_set_p_id:
                    html += '<p id="p%s">' % p_num
                    p_num += 1
                    need_set_p_id = False
                else:
                    html += '<p>'
                paragraph_open = True

            c = ord(d[offset:offset+1])
            # PHTML "functions"
            if c == 0x0:
                offset += 1
                c = ord(d[offset:offset+1])
                # Page link begins
                # 2 Bytes
                # record ID
                if c == 0x0a:
                    offset += 1
                    id = struct.unpack('>H', d[offset:offset+2])[0]
                    if id in self.uid_text_secion_number:
                        html += '<a href="%s.html">' % id
                        link_open = True
                    offset += 1
                # Targeted page link begins
                # 3 Bytes
                # record ID, target
                elif c == 0x0b:
                    offset += 3
                # Paragraph link begins
                # 4 Bytes
                # record ID, paragraph number
                elif c == 0x0c:
                    offset += 1
                    id = struct.unpack('>H', d[offset:offset+2])[0]
                    offset += 2
                    pid = struct.unpack('>H', d[offset:offset+2])[0]
                    if id in self.uid_text_secion_number:
                        html += f'<a href="{id}.html#p{pid}">'
                        link_open = True
                    offset += 1
                # Targeted paragraph link begins
                # 5 Bytes
                # record ID, paragraph number, target
                elif c == 0x0d:
                    offset += 5
                # Link ends
                # 0 Bytes
                elif c == 0x08:
                    if link_open:
                        html += '</a>'
                        link_open = False
                # Set font
                # 1 Bytes
                # font specifier
                elif c == 0x11:
                    offset += 1
                    specifier = d[offset]
                    html += font_specifier_close
                    # Regular text
                    if specifier == 0:
                        font_specifier_close = ''
                    # h1
                    elif specifier == 1:
                        html += '<h1>'
                        font_specifier_close = '</h1>'
                    # h2
                    elif specifier == 2:
                        html += '<h2>'
                        font_specifier_close = '</h2>'
                    # h3
                    elif specifier == 3:
                        html += '<h13>'
                        font_specifier_close = '</h3>'
                    # h4
                    elif specifier == 4:
                        html += '<h4>'
                        font_specifier_close = '</h4>'
                    # h5
                    elif specifier == 5:
                        html += '<h5>'
                        font_specifier_close = '</h5>'
                    # h6
                    elif specifier == 6:
                        html += '<h6>'
                        font_specifier_close = '</h6>'
                    # Bold
                    elif specifier == 7:
                        html += '<b>'
                        font_specifier_close = '</b>'
                    # Fixed-width
                    elif specifier == 8:
                        html += '<tt>'
                        font_specifier_close = '</tt>'
                    # Small
                    elif specifier == 9:
                        html += '<small>'
                        font_specifier_close = '</small>'
                    # Subscript
                    elif specifier == 10:
                        html += '<sub>'
                        font_specifier_close = '</sub>'
                    # Superscript
                    elif specifier == 11:
                        html += '<sup>'
                        font_specifier_close = '</sup>'
                # Embedded image
                # 2 Bytes
                # image record ID
                elif c == 0x1a:
                    offset += 1
                    uid = struct.unpack('>H', d[offset:offset+2])[0]
                    html += '<img src="images/%s.jpg" />' % uid
                    offset += 1
                # Set margin
                # 2 Bytes
                # left margin, right margin
                elif c == 0x22:
                    offset += 2
                # Alignment of text
                # 1 Bytes
                # alignment
                elif c == 0x29:
                    offset += 1
                # Horizontal rule
                # 3 Bytes
                # 8-bit height, 8-bit width (pixels), 8-bit width (%, 1-100)
                elif c == 0x33:
                    offset += 3
                    if paragraph_open:
                        html += '</p>'
                        paragraph_open = False
                    html += '<hr />'
                # New line
                # 0 Bytes
                elif c == 0x38:
                    if paragraph_open:
                        html += '</p>\n'
                        paragraph_open = False
                # Italic text begins
                # 0 Bytes
                elif c == 0x40:
                    html += '<i>'
                # Italic text ends
                # 0 Bytes
                elif c == 0x48:
                    html += '</i>'
                # Set text color
                # 3 Bytes
                # 8-bit red, 8-bit green, 8-bit blue
                elif c == 0x53:
                    offset += 3
                # Multiple embedded image
                # 4 Bytes
                # alternate image record ID, image record ID
                elif c == 0x5c:
                    offset += 3
                    uid = struct.unpack('>H', d[offset:offset+2])[0]
                    html += '<img src="images/%s.jpg" />' % uid
                    offset += 1
                # Underline text begins
                # 0 Bytes
                elif c == 0x60:
                    html += '<u>'
                # Underline text ends
                # 0 Bytes
                elif c == 0x68:
                    html += '</u>'
                # Strike-through text begins
                # 0 Bytes
                elif c == 0x70:
                    html += '<s>'
                # Strike-through text ends
                # 0 Bytes
                elif c == 0x78:
                    html += '</s>'
                # 16-bit Unicode character
                # 3 Bytes
                # alternate text length, 16-bit unicode character
                elif c == 0x83:
                    offset += 3
                # 32-bit Unicode character
                # 5 Bytes
                # alternate text length, 32-bit unicode character
                elif c == 0x85:
                    offset += 5
                # Begin custom font span
                # 6 Bytes
                # font page record ID, X page position, Y page position
                elif c == 0x8e:
                    offset += 6
                # Adjust custom font glyph position
                # 4 Bytes
                # X page position, Y page position
                elif c == 0x8c:
                    offset += 4
                # Change font page
                # 2 Bytes
                # font record ID
                elif c == 0x8a:
                    offset += 2
                # End custom font span
                # 0 Bytes
                elif c == 0x88:
                    pass
                # Begin new table row
                # 0 Bytes
                elif c == 0x90:
                    pass
                # Insert table (or table link)
                # 2 Bytes
                # table record ID
                elif c == 0x92:
                    offset += 2
                # Table cell data
                # 7 Bytes
                # 8-bit alignment, 16-bit image record ID, 8-bit columns, 8-bit rows, 16-bit text length
                elif c == 0x97:
                    offset += 7
                # Exact link modifier
                # 2 Bytes
                # Paragraph Offset (The Exact Link Modifier modifies a Paragraph Link or
                # Targeted Paragraph Link function to specify an exact byte offset within
                # the paragraph. This function must be followed immediately by the
                # function it modifies).
                elif c == 0x9a:
                    offset += 2
            elif c == 0xa0:
                html += '&nbsp;'
            else:
                html += codepoint_to_chr(c)
            offset += 1
            if offset in paragraph_offsets:
                need_set_p_id = True
                if paragraph_open:
                    html += '</p>\n'
                    paragraph_open = False

        if paragraph_open:
            html += '</p>'

        return html
