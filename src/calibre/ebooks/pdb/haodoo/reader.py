# -*- coding: utf-8 -*-

'''
Read content from Haodoo.net pdb file.
'''

__license__   = 'GPL v3'
__copyright__ = '2012, Kan-Ru Chen <kanru@kanru.info>'
__docformat__ = 'restructuredtext en'


import struct
import os

from calibre import prepare_string_for_xml
from calibre.ebooks.pdb.formatreader import FormatReader
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.txt.processor import opf_writer, HTML_TEMPLATE

BPDB_IDENT = b'BOOKMTIT'
UPDB_IDENT = b'BOOKMTIU'

punct_table = {
    u"︵": u"（",
    u"︶": u"）",
    u"︷": u"｛",
    u"︸": u"｝",
    u"︹": u"〔",
    u"︺": u"〕",
    u"︻": u"【",
    u"︼": u"】",
    u"︗": u"〖",
    u"︘": u"〗",
    u"﹇": u"［］",
    u"﹈": u"［］",
    u"︽": u"《",
    u"︾": u"》",
    u"︿": u"〈",
    u"﹀": u"〉",
    u"﹁": u"「",
    u"﹂": u"」",
    u"﹃": u"『",
    u"﹄": u"』",
    u"｜": u"—",
    u"︙": u"…",
    u"ⸯ": u"～",
    u"│": u"…",
    u"￤": u"…",
    u"　": u"  ",
    }

def fix_punct(line):
    for (key, value) in punct_table.items():
        line = line.replace(key, value)
    return line

class LegacyHeaderRecord(object):

    def __init__(self, raw):
        fields = raw.lstrip().replace(b'\x1b\x1b\x1b', b'\x1b').split(b'\x1b')
        self.title = fix_punct(fields[0].decode('cp950', 'replace'))
        self.num_records = int(fields[1])
        self.chapter_titles = map(
            lambda x: fix_punct(x.decode('cp950', 'replace').rstrip(b'\x00')),
            fields[2:])

class UnicodeHeaderRecord(object):

    def __init__(self, raw):
        fields = raw.lstrip().replace(b'\x1b\x00\x1b\x00\x1b\x00',
                b'\x1b\x00').split(b'\x1b\x00')
        self.title = fix_punct(fields[0].decode('utf_16_le', 'ignore'))
        self.num_records = int(fields[1])
        self.chapter_titles = map(
            lambda x: fix_punct(x.decode('utf_16_le', 'replace').rstrip(b'\x00')),
            fields[2].split(b'\r\x00\n\x00'))

class Reader(FormatReader):

    def __init__(self, header, stream, log, options):
        self.stream = stream
        self.log = log

        self.sections = []
        for i in range(header.num_sections):
            self.sections.append(header.section_data(i))

        if header.ident == BPDB_IDENT:
            self.header_record = LegacyHeaderRecord(self.section_data(0))
            self.encoding = 'cp950'
        else:
            self.header_record = UnicodeHeaderRecord(self.section_data(0))
            self.encoding = 'utf_16_le'

    def author(self):
        self.stream.seek(35)
        version = struct.unpack(b'>b', self.stream.read(1))[0]
        if version == 2:
            self.stream.seek(0)
            author = self.stream.read(35).rstrip(b'\x00').decode(self.encoding, 'replace')
            return author
        else:
            return u'Unknown'

    def get_metadata(self):
        mi = MetaInformation(self.header_record.title,
                             [self.author()])
        mi.language = u'zh-tw'

        return mi

    def section_data(self, number):
        return self.sections[number]

    def decompress_text(self, number):
        return self.section_data(number).decode(self.encoding,
                'replace').rstrip(b'\x00')

    def extract_content(self, output_dir):
        txt = u''

        self.log.info(u'Decompressing text...')
        for i in range(1, self.header_record.num_records + 1):
            self.log.debug(u'\tDecompressing text section %i' % i)
            title = self.header_record.chapter_titles[i-1]
            lines = []
            title_added = False
            for line in self.decompress_text(i).splitlines():
                line = fix_punct(line)
                line = line.strip()
                if not title_added and title in line:
                    line = u'<h1 class="chapter">' + line + u'</h1>\n'
                    title_added = True
                else:
                    line = prepare_string_for_xml(line)
                lines.append(u'<p>%s</p>' % line)
            if not title_added:
                lines.insert(0, u'<h1 class="chapter">' + title + u'</h1>\n')
            txt += u'\n'.join(lines)

        self.log.info(u'Converting text to OEB...')
        html = HTML_TEMPLATE % (self.header_record.title, txt)
        with open(os.path.join(output_dir, u'index.html'), 'wb') as index:
            index.write(html.encode('utf-8'))

        mi = self.get_metadata()
        manifest = [(u'index.html', None)]
        spine = [u'index.html']
        opf_writer(output_dir, u'metadata.opf', manifest, spine, mi)

        return os.path.join(output_dir, u'metadata.opf')
