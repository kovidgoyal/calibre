# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Device driver for Hanvon devices
'''

from calibre.devices.usbms.driver import USBMS

class N516(USBMS):

    name           = 'N516 driver'
    gui_name       = 'N516'
    description    = _('Communicate with the Hanvon N520 eBook reader.')
    author         = 'John Schember'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'prc', 'html', 'pdf', 'txt']

    VENDOR_ID   = [0x0525]
    PRODUCT_ID  = [0xa4a5]
    BCD         = [0x323]

    VENDOR_NAME      = 'INGENIC'
    WINDOWS_MAIN_MEM = '_FILE-STOR_GADGE'

    MAIN_MEMORY_VOLUME_LABEL  = 'N520 Internal Memory'

    EBOOK_DIR_MAIN = 'e_book'
    SUPPORTS_SUB_DIRS = True
