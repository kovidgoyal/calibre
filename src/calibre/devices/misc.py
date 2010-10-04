#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from calibre.devices.usbms.driver import USBMS

class PALMPRE(USBMS):

    name           = 'Palm Pre Device Interface'
    gui_name       = 'Palm Pre'
    description    = _('Communicate with the Palm Pre')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'mobi', 'prc', 'pdb', 'txt']

    VENDOR_ID   = [0x0830]
    PRODUCT_ID  = [0x8004, 0x8002, 0x0101]
    BCD         = [0x0316]

    VENDOR_NAME = 'PALM'
    WINDOWS_MAIN_MEM = 'PRE'

    EBOOK_DIR_MAIN = 'E-books'


class AVANT(USBMS):
    name           = 'Booq Avant Device Interface'
    gui_name       = 'Avant'
    description    = _('Communicate with the Booq Avant')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'fb2', 'html', 'rtf', 'pdf', 'txt']

    VENDOR_ID   = [0x0525]
    PRODUCT_ID  = [0xa4a5]
    BCD         = [0x0319]

    VENDOR_NAME = 'E-BOOK'
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = 'READER'

    EBOOK_DIR_MAIN = ''
    SUPPORTS_SUB_DIRS = True

class SWEEX(USBMS):
    # Identical to the Promedia
    name           = 'Sweex Device Interface'
    gui_name       = 'Sweex'
    description    = _('Communicate with the Sweex MM300')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'prc', 'fb2', 'html', 'rtf', 'chm', 'pdf', 'txt']

    VENDOR_ID   = [0x0525]
    PRODUCT_ID  = [0xa4a5]
    BCD         = [0x0319]

    VENDOR_NAME = 'SWEEX'
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = 'EBOOKREADER'

    EBOOK_DIR_MAIN = ''
    SUPPORTS_SUB_DIRS = True

class KOGAN(SWEEX):

    name           = 'Kogan Device Interface'
    gui_name       = 'Kogan'
    description    = _('Communicate with the Kogan')
    VENDOR_NAME = 'LINUX'
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = 'FILE-STOR_GADGET'
    EBOOK_DIR_MAIN = 'Kogan eBooks'

class PDNOVEL(USBMS):
    name = 'Pandigital Novel device interface'
    gui_name = 'PD Novel'
    description = _('Communicate with the Pandigital Novel')
    author = 'Kovid Goyal'
    supported_platforms = ['windows', 'linux', 'osx']
    FORMATS = ['epub', 'pdf']

    VENDOR_ID   = [0x18d1]
    PRODUCT_ID  = [0xb004]
    BCD         = [0x224]

    VENDOR_NAME = 'ANDROID'
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = '__UMS_COMPOSITE'
    THUMBNAIL_HEIGHT = 144

    EBOOK_DIR_MAIN = 'eBooks'
    SUPPORTS_SUB_DIRS = False
    DELETE_EXTS = ['.jpg', '.jpeg', '.png']


    def upload_cover(self, path, filename, metadata):
        coverdata = getattr(metadata, 'thumbnail', None)
        if coverdata and coverdata[2]:
            with open('%s.jpg' % os.path.join(path, filename), 'wb') as coverfile:
                coverfile.write(coverdata[2])

class VELOCITYMICRO(USBMS):
    name = 'VelocityMicro device interface'
    gui_name = 'VelocityMicro'
    description = _('Communicate with the VelocityMicro')
    author = 'Kovid Goyal'
    supported_platforms = ['windows', 'linux', 'osx']
    FORMATS = ['epub', 'pdb', 'txt', 'html', 'pdf']

    VENDOR_ID   = [0x18d1]
    PRODUCT_ID  = [0xb015]
    BCD         = [0x224]

    VENDOR_NAME = 'ANDROID'
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = '__UMS_COMPOSITE'

    EBOOK_DIR_MAIN = 'eBooks'
    SUPPORTS_SUB_DIRS = False

class GEMEI(USBMS):
    name           = 'Gemei Device Interface'
    gui_name       = 'GM2000'
    description    = _('Communicate with the GM2000')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'chm', 'html', 'pdb', 'pdf', 'txt']

    VENDOR_ID   = [0x07c4]
    PRODUCT_ID  = [0xa4a5]
    BCD         = None

    VENDOR_NAME = 'CHINA'
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = 'CHIP'

    EBOOK_DIR_MAIN = 'eBooks'
    SUPPORTS_SUB_DIRS = True

