# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Device driver for Bookeen's Cybook Gen 3
'''

import os

from calibre.constants import isunix
from calibre.devices.usbms.driver import USBMS
import calibre.devices.cybookg3.t2b as t2b

class CYBOOKG3(USBMS):

    name           = 'Cybook Gen 3 Device Interface'
    gui_name       = 'Cybook Gen 3'
    description    = _('Communicate with the Cybook Gen 3 eBook reader.')
    author         = 'John Schember'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    # Be sure these have an entry in calibre.devices.mime
    FORMATS     = ['epub', 'mobi', 'prc', 'html', 'pdf', 'rtf', 'txt']

    VENDOR_ID   = [0x0bda, 0x3034]
    PRODUCT_ID  = [0x0703, 0x1795]
    BCD         = [0x110, 0x132]

    VENDOR_NAME = 'BOOKEEN'
    WINDOWS_MAIN_MEM = 'CYBOOK_GEN3__-FD'
    WINDOWS_CARD_A_MEM = 'CYBOOK_GEN3__-SD'

    OSX_MAIN_MEM = 'Bookeen Cybook Gen3 -FD Media'
    OSX_CARD_A_MEM = 'Bookeen Cybook Gen3 -SD Media'

    MAIN_MEMORY_VOLUME_LABEL  = 'Cybook Gen 3 Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'Cybook Gen 3 Storage Card'

    EBOOK_DIR_MAIN = 'eBooks'
    EBOOK_DIR_CARD_A = 'eBooks'
    THUMBNAIL_HEIGHT = 144
    DELETE_EXTS = ['.mbp', '.dat', '_6090.t2b']
    SUPPORTS_SUB_DIRS = True

    def upload_cover(self, path, filename, metadata):
        coverdata = getattr(metadata, 'thumbnail', None)
        if coverdata:
            with open('%s_6090.t2b' % os.path.join(path, filename), 'wb') as t2bfile:
                t2b.write_t2b(t2bfile, coverdata)

    @classmethod
    def can_handle(cls, device_info, debug=False):
        if isunix:
            return device_info[3] == 'Bookeen' and device_info[4] == 'Cybook Gen3'
        return True


class CYBOOK_OPUS(CYBOOKG3):

    name           = 'Cybook Opus Device Interface'
    gui_name       = 'Cybook Opus'
    description    = _('Communicate with the Cybook Opus eBook reader.')
    author         = 'John Schember'
    supported_platforms = ['windows', 'osx', 'linux']

    FORMATS = ['epub', 'pdf', 'txt']

    VENDOR_ID   = [0x0bda]
    PRODUCT_ID  = [0x0703]
    BCD         = [0x110]

    VENDOR_NAME = 'BOOKEEN'
    WINDOWS_MAIN_MEM = 'CYBOOK_OPUS__-FD'
    WINDOWS_CARD_A_MEM = 'CYBOOK_OPUS__-SD'

    OSX_MAIN_MEM = 'Bookeen Cybook Opus -FD Media'
    OSX_CARD_A_MEM = 'Bookeen Cybook Opus -SD Media'

    EBOOK_DIR_MAIN = 'eBooks'
    EBOOK_DIR_CARD_A = 'eBooks'
    SUPPORTS_SUB_DIRS = True

    @classmethod
    def can_handle(cls, device_info, debug=False):
        if isunix:
            return device_info[3] == 'Bookeen'
        return True
