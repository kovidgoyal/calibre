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

from calibre.devices.usbms.driver import USBMS
from calibre.ebooks.metadata import string_to_authors

class JETBOOK(USBMS):
    name           = 'Ectaco JetBook Device Interface'
    description    = _('Communicate with the JetBook eBook reader.')
    author         = 'James Ralston'
    supported_platforms = ['windows', 'osx', 'linux']


    # Ordered list of supported formats
    # Be sure these have an entry in calibre.devices.mime
    FORMATS     = ['epub', 'mobi', 'prc', 'fb2', 'txt', 'rtf', 'pdf']

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

    def filename_callback(self, fname, mi):
        fileext = os.path.splitext(os.path.basename(fname))[1]
        if fileext.lower() not in ('txt', 'pdf', 'fb2'):
            return fname
        title = mi.title if mi.title else 'Unknown'
        title = title.replace(' ', '_')
        au = mi.format_authors()
        if not au:
            au = 'Unknown'
        return '%s#%s%s' % (au, title, fileext)

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

class MIBUK(USBMS):

    name           = 'MiBuk Wolder Device Interface'
    description    = _('Communicate with the MiBuk Wolder reader.')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows']

    FORMATS     = ['epub', 'mobi', 'prc', 'fb2', 'txt', 'rtf', 'pdf']

    VENDOR_ID   = [0x0525]
    PRODUCT_ID  = [0xa4a5]
    BCD         = [0x314, 0x319]
    SUPPORTS_SUB_DIRS = True

    VENDOR_NAME      = ['LINUX', 'FILE_BAC']
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = ['WOLDERMIBUK', 'KED_STORAGE_GADG']

class JETBOOK_MINI(USBMS):

    '''
    ['0x4b8',
  '0x507',
  '0x100',
  'ECTACO',
  'ECTACO ATA/ATAPI Bridge (Bulk-Only)',
  'Rev.0.20']
    '''
    FORMATS     = ['fb2', 'txt']

    gui_name = 'JetBook Mini'
    name = 'JetBook Mini Device Interface'
    description    = _('Communicate with the JetBook Mini reader.')
    author         = 'Kovid Goyal'

    VENDOR_ID = [0x4b8]
    PRODUCT_ID = [0x507]
    BCD = [0x100]
    VENDOR_NAME      = 'ECTACO'
    WINDOWS_MAIN_MEM = '' # Matches PROD_
    MAIN_MEMORY_VOLUME_LABEL  = 'Jetbook Mini'

    SUPPORTS_SUB_DIRS = True

class JETBOOK_COLOR(USBMS):

    '''
set([(u'0x951',
      u'0x160b',
      u'0x0',
      u'Freescale',
      u'Mass Storage Device',
      u'0802270905553')])
    '''

    FORMATS = ['epub', 'mobi', 'prc', 'fb2', 'rtf', 'txt', 'pdf', 'djvu']

    gui_name = 'JetBook Color'
    name = 'JetBook Color Device Interface'
    description    = _('Communicate with the JetBook Color reader.')
    author         = 'Kovid Goyal'

    VENDOR_ID = [0x951]
    PRODUCT_ID = [0x160b]
    BCD = [0x0]
    EBOOK_DIR_MAIN = 'My Books'

    SUPPORTS_SUB_DIRS = True


