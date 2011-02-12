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
    Currently uses the Adobe 1024 byte count equal one page formula.
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
            count += 1024

        return pages
