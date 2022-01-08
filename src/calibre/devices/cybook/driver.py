__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Device driver for Bookeen's Cybook Gen 3 and Opus and Orizon
'''

import os
import re

from calibre import fsync
from calibre.constants import isunix
from calibre.devices.usbms.driver import USBMS
import calibre.devices.cybook.t2b as t2b
import calibre.devices.cybook.t4b as t4b


class CYBOOK(USBMS):

    name           = 'Cybook Gen 3 / Opus Device Interface'
    gui_name       = 'Cybook Gen 3/Opus'
    description    = _('Communicate with the Cybook Gen 3/Opus e-book reader.')
    author         = 'John Schember'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    # Be sure these have an entry in calibre.devices.mime
    FORMATS     = ['epub', 'mobi', 'prc', 'html', 'pdf', 'rtf', 'txt']

    VENDOR_ID   = [0x0bda, 0x3034]
    PRODUCT_ID  = [0x0703, 0x1795]
    BCD         = [0x110, 0x132]

    VENDOR_NAME = 'BOOKEEN'
    WINDOWS_MAIN_MEM = re.compile(r'CYBOOK_(OPUS|GEN3)__-FD')
    WINDOWS_CARD_A_MEM = re.compile('CYBOOK_(OPUS|GEN3)__-SD')
    OSX_MAIN_MEM_VOL_PAT = re.compile(r'/Cybook')

    EBOOK_DIR_MAIN = 'eBooks'
    EBOOK_DIR_CARD_A = 'eBooks'
    THUMBNAIL_HEIGHT = 144
    DELETE_EXTS = ['.mbp', '.dat', '.bin', '_6090.t2b', '.thn']
    SUPPORTS_SUB_DIRS = True

    def upload_cover(self, path, filename, metadata, filepath):
        coverdata = getattr(metadata, 'thumbnail', None)
        if coverdata and coverdata[2]:
            coverdata = coverdata[2]
        else:
            coverdata = None
        with lopen('%s_6090.t2b' % os.path.join(path, filename), 'wb') as t2bfile:
            t2b.write_t2b(t2bfile, coverdata)
            fsync(t2bfile)

    @classmethod
    def can_handle(cls, device_info, debug=False):
        if isunix:
            return device_info[3] == 'Bookeen' and (device_info[4] == 'Cybook Gen3' or device_info[4] == 'Cybook Opus')
        return True


class ORIZON(CYBOOK):

    name           = 'Cybook Orizon Device Interface'
    gui_name       = 'Orizon'
    description    = _('Communicate with the Cybook Orizon e-book reader.')

    BCD         = [0x319]

    FORMATS     = ['epub', 'html', 'pdf', 'rtf', 'txt']

    VENDOR_NAME = ['BOOKEEN', 'LINUX']
    WINDOWS_MAIN_MEM = re.compile(r'(CYBOOK_ORIZON__-FD)|(FILE-STOR_GADGET)')
    WINDOWS_CARD_A_MEM = re.compile('(CYBOOK_ORIZON__-SD)|(FILE-STOR_GADGET)')

    EBOOK_DIR_MAIN = EBOOK_DIR_CARD_A = 'Digital Editions'

    EXTRA_CUSTOMIZATION_MESSAGE = [
        _('Card A folder') + ':::<p>' + _(
            'Enter the folder where the books are to be stored when sent to the '
            'memory card. This folder is prepended to any send to device template') + '</p>',
    ]
    EXTRA_CUSTOMIZATION_DEFAULT = [EBOOK_DIR_CARD_A]

    def upload_cover(self, path, filename, metadata, filepath):
        coverdata = getattr(metadata, 'thumbnail', None)
        if coverdata and coverdata[2]:
            coverdata = coverdata[2]
        else:
            coverdata = None
        with lopen('%s.thn' % filepath, 'wb') as thnfile:
            t4b.write_t4b(thnfile, coverdata)
            fsync(thnfile)

    def post_open_callback(self):
        opts = self.settings()
        folder = opts.extra_customization[0]
        if not folder:
            folder = ''
        self.EBOOK_DIR_CARD_A = folder

    @classmethod
    def can_handle(cls, device_info, debug=False):
        if isunix:
            return device_info[3] == 'Bookeen' and device_info[4] == 'Cybook Orizon'
        return True

    def get_carda_ebook_dir(self, for_upload=False):
        if not for_upload:
            return ''
        return self.EBOOK_DIR_CARD_A


class MUSE(CYBOOK):

    name           = 'Cybook Muse Device Interface'
    gui_name       = 'Muse'
    description    = _('Communicate with the Cybook Muse e-book reader.')
    author         = 'Kovid Goyal'

    FORMATS     = ['epub', 'html', 'fb2', 'txt', 'pdf', 'djvu']

    VENDOR_ID   = [0x0525]
    PRODUCT_ID  = [0xa4a5]
    BCD         = [0x0230]

    VENDOR_NAME = 'USB_2.0'
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = 'USB_FLASH_DRIVER'

    EBOOK_DIR_MAIN = 'Books'
    SCAN_FROM_ROOT = True

    @classmethod
    def can_handle(cls, device_info, debug=False):
        if isunix:
            return device_info[3] == 'Bookeen' and device_info[4] in ('Cybook', 'Lev', 'Nolimbook', 'Letto', 'Nolim', 'Saga', 'NolimbookXL')
        return True


class DIVA(CYBOOK):

    name           = 'Bookeen Diva HD Device Interface'
    gui_name       = 'Diva HD'
    description    = _('Communicate with the Bookeen Diva HD e-book reader.')
    author         = 'Kovid Goyal'

    VENDOR_ID = [0x1d6b]
    PRODUCT_ID = [0x0104]
    BCD = [0x100]

    FORMATS     = ['epub', 'html', 'fb2', 'txt', 'pdf']
    EBOOK_DIR_MAIN = 'Books'
    SCAN_FROM_ROOT = True

    @classmethod
    def can_handle(cls, device_info, debug=False):
        return True
