# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2011, John Schember <john at nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Generates and writes an APNX page mapping file.
'''

import struct
import uuid

from calibre.ebooks.pdb.header import PdbHeaderReader

class APNXBuilder(object):
    '''
    2300 characters of uncompressed text per page. This is
    not meant to map 1 to 1 to a print book but to be a
    close enough measure.
    
    A test book was chosen and the characters were counted
    on one page. This number was round to 2240 then 60
    characters of markup were added to the total giving
    2300.
    
    Uncompressed text length is used because it's easily
    accessible in MOBI files (part of the header). Also,
    It's faster to work off of the length then to
    decompress and parse the actual text.
    
    A better but much more resource intensive and slower
    method to calculate the page length would be to parse
    the uncompressed text. For each paragraph we would
    want to find how many lines it would occupy in a paper
    back book. 70 characters per line and 32 lines per page.
    So divide the number of characters (minus markup) in
    each paragraph by 70. If there are less than 70
    characters in the paragraph then it is 1 line. Then,
    count every 32 lines and mark that location as a page.
    '''

    def write_apnx(self, mobi_file_path, apnx_path):
        with open(mobi_file_path, 'rb') as mf:
            phead = PdbHeaderReader(mf)
            r0 = phead.section_data(0)
            text_length = struct.unpack('>I', r0[4:8])[0]

        pages = self.get_pages(text_length)
        apnx = self.generate_apnx(pages)

        with open(apnx_path, 'wb') as apnxf:
            apnxf.write(apnx)

    def generate_apnx(self, pages):
        apnx = ''

        content_vals = {
            'guid': str(uuid.uuid4()).replace('-', '')[:8],
            'isbn': '',
        }

        content_header = '{"contentGuid":"%(guid)s","asin":"%(isbn)s","cdeType":"EBOK","fileRevisionId":"1"}' % content_vals
        page_header = '{"asin":"%(isbn)s","pageMap":"(1,a,1)"}' % content_vals

        apnx += struct.pack('>I', 65537)
        apnx += struct.pack('>I', 12 + len(content_header))
        apnx += struct.pack('>I', len(content_header))
        apnx += content_header
        apnx += struct.pack('>H', 1)
        apnx += struct.pack('>H', len(page_header))
        apnx += struct.pack('>H', len(pages))
        apnx += struct.pack('>H', 32)
        apnx += page_header

        # write page values to apnx
        for page in pages:
            apnx += struct.pack('>L', page)

        return apnx

    def get_pages(self, text_length):
        pages = []
        count = 0

        while count < text_length:
            pages.append(count)
            count += 2300

        return pages
