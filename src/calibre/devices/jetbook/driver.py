# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, James Ralston <jralston at mindspring.com>'
__docformat__ = 'restructuredtext en'

'''
Device driver for Ectaco Jetbook firmware >= JL04_v030e
'''

import os
import re
import sys
from itertools import cycle

from calibre.devices.usbms.driver import USBMS
from calibre.utils.filenames import ascii_filename as sanitize
from calibre.ebooks.metadata import string_to_authors

class JETBOOK(USBMS):
    name           = 'Ectaco JetBook Device Interface'
    description    = _('Communicate with the JetBook eBook reader.')
    author         = _('James Ralston')
    supported_platforms = ['windows', 'osx', 'linux']


    # Ordered list of supported formats
    # Be sure these have an entry in calibre.devices.mime
    FORMATS     = ['epub', 'mobi', 'prc', 'txt', 'rtf', 'pdf']

    VENDOR_ID   = [0x0525]
    PRODUCT_ID  = [0xa4a5]
    BCD         = [0x314]

    VENDOR_NAME      = 'LINUX'
    WINDOWS_MAIN_MEM = 'EBOOK'
    WINDOWS_CARD_A_MEM = 'EBOOK'

    OSX_MAIN_MEM = 'Linux ebook Media'
    OSX_CARD_A_MEM = 'Linux ebook Media'

    MAIN_MEMORY_VOLUME_LABEL  = 'Jetbook Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'Jetbook Storage Card'

    EBOOK_DIR_MAIN = "Books"
    EBOOK_DIR_CARD_A = "Books"
    SUPPORTS_SUB_DIRS = True

    JETBOOK_FILE_NAME_PATTERN = re.compile(
            r'(?P<authors>.+)#(?P<title>.+)'
            )

    def upload_books(self, files, names, on_card=False, end_session=True,
                    metadata=None):

        base_path = self._sanity_check(on_card, files)

        paths = []
        names = iter(names)
        metadata = iter(metadata)

        for i, infile in enumerate(files):
            mdata, fname = metadata.next(), names.next()
            path = os.path.dirname(self.create_upload_path(base_path, mdata, fname))

            author = sanitize(mdata.get('authors','Unknown')).replace(' ', '_')
            title = sanitize(mdata.get('title', 'Unknown')).replace(' ', '_')
            fileext = os.path.splitext(os.path.basename(fname))[1]
            fname = '%s#%s%s' % (author, title, fileext)

            filepath = os.path.join(path, fname)
            paths.append(filepath)

            self.put_file(infile, filepath, replace_file=True)

            self.report_progress((i+1) / float(len(files)), _('Transferring books to device...'))

        self.report_progress(1.0, _('Transferring books to device...'))

        return zip(paths, cycle([on_card]))

    @classmethod
    def metadata_from_path(cls, path):

        def check_unicode(txt):
            txt = txt.replace('_', ' ')
            if not isinstance(txt, unicode):
                return txt.decode(sys.getfilesystemencoding(), 'replace')

            return txt

        mi = cls.metadata_from_formats([path])

        if (mi.title==_('Unknown') or mi.authors==[_('Unknown')]) \
                and '#' in mi.title:
            fn = os.path.splitext(os.path.basename(path))[0]
            match = cls.JETBOOK_FILE_NAME_PATTERN.match(fn)
            if match is not None:
                mi.title = check_unicode(match.group('title'))
                authors = string_to_authors(match.group('authors'))
                mi.authors = map(check_unicode, authors)

        return mi

    def windows_sort_drives(self, drives):
        main = drives.get('main', None)
        card = drives.get('carda', None)
        if card and main and card < main:
            drives['main'] = card
            drives['carda'] = main

        return drives
