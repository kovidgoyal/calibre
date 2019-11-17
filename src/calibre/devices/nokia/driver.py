# -*- coding: utf-8 -*-


__license__   = 'GPL v3'
__copyright__ = '2009-2014, John Schember <john at nachtimwald.com> and Andres Gomez <agomez at igalia.com>'
__docformat__ = 'restructuredtext en'

'''
Device driver for Nokia's internet tablet devices
'''

from calibre.devices.usbms.driver import USBMS


class N770(USBMS):

    name           = 'Nokia 770 Device Interface'
    gui_name       = 'Nokia 770'
    description    = _('Communicate with the Nokia 770 Internet Tablet.')
    author         = 'John Schember and Andres Gomez'
    supported_platforms = ['windows', 'linux', 'osx']

    # Ordered list of supported formats
    FORMATS     = ['mobi', 'prc', 'epub', 'pdf', 'html', 'zip', 'fb2', 'chm',
        'pdb', 'tcr', 'txt', 'rtf']

    VENDOR_ID   = [0x421]
    PRODUCT_ID  = [0x431]
    BCD         = [0x308]

    VENDOR_NAME      = 'NOKIA'
    WINDOWS_MAIN_MEM = '770'

    MAIN_MEMORY_VOLUME_LABEL  = 'Nokia 770 Main Memory'

    EBOOK_DIR_MAIN = 'My Ebooks'
    SUPPORTS_SUB_DIRS = True


class N810(N770):
    name           = 'Nokia N800/N810/N900/N950/N9 Device Interface'
    gui_name       = 'Nokia N800/N810/N900/N950/N9'
    description    = _('Communicate with the Nokia N800/N810/N900/N950/N9 Maemo/MeeGo devices.')

    PRODUCT_ID = [0x4c3, 0x96, 0x1c7, 0x3d1, 0x518]
    BCD        = [0x316]

    WINDOWS_MAIN_MEM = ['N800', 'N810', 'N900', 'NOKIA_N950', 'NOKIA_N9']

    MAIN_MEMORY_VOLUME_LABEL = 'Nokia Maemo/MeeGo device Main Memory'


class E71X(USBMS):

    name           = 'Nokia E71X device interface'
    gui_name       = 'Nokia E71X'
    description    = _('Communicate with the Nokia E71X')
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
