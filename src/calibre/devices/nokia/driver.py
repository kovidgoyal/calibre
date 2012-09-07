# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Device driver for Nokia's internet tablet devices
'''

from calibre.devices.usbms.driver import USBMS

class N770(USBMS):

    name           = 'Nokia 770 Device Interface'
    gui_name       = 'Nokia 770'
    description    = _('Communicate with the Nokia 770 internet tablet.')
    author         = 'John Schember'
    supported_platforms = ['windows', 'linux', 'osx']

    # Ordered list of supported formats
    FORMATS     = ['mobi', 'prc', 'epub', 'html', 'zip', 'fb2', 'chm', 'pdb',
        'tcr', 'txt', 'rtf']

    VENDOR_ID   = [0x421]
    PRODUCT_ID  = [0x431]
    BCD         = [0x308]

    VENDOR_NAME      = 'NOKIA'
    WINDOWS_MAIN_MEM = '770'

    MAIN_MEMORY_VOLUME_LABEL  = 'N770 Main Memory'

    EBOOK_DIR_MAIN = 'My Ebooks'
    SUPPORTS_SUB_DIRS = True

class N810(N770):
    name           = 'Nokia 810 Device Interface'
    gui_name       = 'Nokia 810/900/9'
    description    = _('Communicate with the Nokia 810/900 internet tablet.')

    PRODUCT_ID = [0x96, 0x1c7, 0x0518]
    BCD        = [0x316]

    WINDOWS_MAIN_MEM = ['N810', 'N900', 'NOKIA_N9']

    MAIN_MEMORY_VOLUME_LABEL = 'Nokia Tablet Main Memory'

class E71X(USBMS):

    name           = 'Nokia E71X device interface'
    gui_name       = 'Nokia E71X'
    description    = 'Communicate with the Nokia E71X'
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'linux', 'osx']

    VENDOR_ID   = [0x421]
    PRODUCT_ID  = [0x1a0]
    BCD         = [0x100]


    FORMATS = ['mobi', 'prc']

    EBOOK_DIR_MAIN = 'eBooks'
    SUPPORTS_SUB_DIRS = True

    VENDOR_NAME      = 'NOKIA'
    WINDOWS_MAIN_MEM = 'S60'

class E52(USBMS):

    name = 'Nokia E52 device interface'
    gui_name = 'Nokia E52'
    description = _('Communicate with the Nokia E52')
    author = 'David Ignjic'
    supported_platforms = ['windows', 'linux', 'osx']

    VENDOR_ID = [0x421]
    PRODUCT_ID = [0x1CD, 0x273, 0x00aa]
    BCD = [0x100]


    FORMATS = ['epub', 'fb2', 'mobi', 'prc', 'txt']

    EBOOK_DIR_MAIN = 'eBooks'
    SUPPORTS_SUB_DIRS = True

    VENDOR_NAME = 'NOKIA'
    WINDOWS_MAIN_MEM = ['S60', 'E71']

