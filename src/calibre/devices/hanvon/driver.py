# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Device driver for Hanvon devices
'''
import re

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
    BCD         = [0x323, 0x326]

    VENDOR_NAME      = 'INGENIC'
    WINDOWS_MAIN_MEM = '_FILE-STOR_GADGE'

    MAIN_MEMORY_VOLUME_LABEL  = 'N520 Internal Memory'

    EBOOK_DIR_MAIN = 'e_book'
    SUPPORTS_SUB_DIRS = True

class ALEX(N516):

    name = 'Alex driver'
    gui_name = 'SpringDesign Alex'
    description    = _('Communicate with the SpringDesign Alex eBook reader.')
    author         = 'Kovid Goyal'

    FORMATS     = ['epub', 'pdf']
    VENDOR_NAME      = 'ALEX'
    WINDOWS_MAIN_MEM = 'READER'

    MAIN_MEMORY_VOLUME_LABEL  = 'Alex Internal Memory'

    EBOOK_DIR_MAIN = 'eBooks'
    SUPPORTS_SUB_DIRS = True

class EB511(USBMS):
    name           = 'Elonex EB 511 driver'
    gui_name       = 'EB 511'
    description    = _('Communicate with the Elonex EB 511 eBook reader.')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']

    FORMATS     = ['epub', 'html', 'pdf', 'txt']

    VENDOR_ID   = [0x45e]
    PRODUCT_ID  = [0xffff]
    BCD         = [0x0]

    MAIN_MEMORY_VOLUME_LABEL  = 'EB 511 Internal Memory'

    EBOOK_DIR_MAIN = 'e_book'
    SUPPORTS_SUB_DIRS = True

    OSX_MAIN_MEM_VOL_PAT = re.compile(r'/eReader')


