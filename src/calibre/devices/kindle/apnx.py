# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2011, John Schember <john at nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Generates and writes an APNX page mapping file.
'''

import struct

from calibre.ebooks.mobi.reader.mobi6 import MobiReader
from calibre.ebooks.pdb.header import PdbHeaderReader
from calibre.utils.logging import default_log

class APNXBuilder(object):
    '''
    Create an APNX file using a pseudo page mapping.
    '''

    def write_apnx(self, mobi_file_path, apnx_path, accurate=True, page_count=0):
        '''
        If you want a fixed number of pages (such as from a custom column) then
        pass in a value to page_count, otherwise a count will be estimated
        using either the fast or accurate algorithm.
        '''
        # Check that this is really a MOBI file.
        with open(mobi_file_path, 'rb') as mf:
            ident = PdbHeaderReader(mf).identity()
        if ident != 'BOOKMOBI':
            raise Exception(_('Not a valid MOBI file. Reports identity of %s') % ident)

        # Get the pages depending on the chosen parser
        pages = []
        if page_count:
            pages = self.get_pages_exact(mobi_file_path, page_count)
        else:
            if accurate:
                try:
                    pages = self.get_pages_accurate(mobi_file_path)
                except:
                    # Fall back to the fast parser if we can't
                    # use the accurate one. Typically this is
                    # due to the file having DRM.
                    pages = self.get_pages_fast(mobi_file_path)
            else:
                pages = self.get_pages_fast(mobi_file_path)

        if not pages:
            raise Exception(_('Could not generate page mapping.'))

        # Generate the APNX file from the page mapping.
        apnx = self.generate_apnx(pages)

        # Write the APNX.
        with open(apnx_path, 'wb') as apnxf:
            apnxf.write(apnx)

    def generate_apnx(self, pages):
        import uuid
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

        # Write page values to APNX.
        for page in pages:
            apnx += struct.pack('>I', page)

        return apnx

    def get_pages_exact(self, mobi_file_path, page_count):
        '''
        Given a specified page count (such as from a custom column),
        create our array of pages for the apnx file by dividing by
        the content size of the book.
        '''
        pages = []
        count = 0

        with open(mobi_file_path, 'rb') as mf:
            phead = PdbHeaderReader(mf)
            r0 = phead.section_data(0)
            text_length = struct.unpack('>I', r0[4:8])[0]

        chars_per_page = int(text_length / page_count)
        while count < text_length:
            pages.append(count)
            count += chars_per_page

        if len(pages) > page_count:
            # Rounding created extra page entries
            pages = pages[:page_count]

        return pages

    def get_pages_fast(self, mobi_file_path):
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
        '''
        text_length = 0
        pages = []
        count = 0

        with open(mobi_file_path, 'rb') as mf:
            phead = PdbHeaderReader(mf)
            r0 = phead.section_data(0)
            text_length = struct.unpack('>I', r0[4:8])[0]

        while count < text_length:
            pages.append(count)
            count += 2300

        return pages

    def get_pages_accurate(self, mobi_file_path):
        '''
        A more accurate but much more resource intensive and slower
        method to calculate the page length.

        Parses the uncompressed text. In an average paper back book
        There are 32 lines per page and a maximum of 70 characters
        per line.

        Each paragraph starts a new line and every 70 characters
        (minus markup) in a paragraph starts a new line. The
        position after every 30 lines will be marked as a new
        page.

        This can be make more accurate by accounting for
        <div class="mbp_pagebreak" /> as a new page marker.
        And <br> elements as an empty line.
        '''
        pages = []

        # Get the MOBI html.
        mr = MobiReader(mobi_file_path, default_log)
        if mr.book_header.encryption_type != 0:
            # DRMed book
            return self.get_pages_fast(mobi_file_path)
        mr.extract_text()

        # States
        in_tag = False
        in_p = False
        check_p = False
        closing = False
        p_char_count = 0

        # Get positions of every line
        # A line is either a paragraph starting
        # or every 70 characters in a paragraph.
        lines = []
        pos = -1
        # We want this to be as fast as possible so we
        # are going to do one pass across the text. re
        # and string functions will parse the text each
        # time they are called.
        #
        # We can can use .lower() here because we are
        # not modifying the text. In this case the case
        # doesn't matter just the absolute character and
        # the position within the stream.
        for c in mr.mobi_html.lower():
            pos += 1

            # Check if we are starting or stopping a p tag.
            if check_p:
                if c == '/':
                    closing = True
                    continue
                elif c == 'p':
                    if closing:
                        in_p = False
                    else:
                        in_p = True
                        lines.append(pos - 2)
                check_p = False
                closing = False
                continue

            if c == '<':
                in_tag = True
                check_p = True
                continue
            elif c == '>':
                in_tag = False
                check_p = False
                continue

            if in_p and not in_tag:
                p_char_count += 1
                if p_char_count == 70:
                    lines.append(pos)
                    p_char_count = 0

        # Every 30 lines is a new page
        for i in xrange(0, len(lines), 32):
            pages.append(lines[i])

        return pages
