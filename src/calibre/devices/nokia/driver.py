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
    description    = _('Communicate with the Nokia Nokia 770 internet tablet.')
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
    gui_name       = 'Nokia 810'
    description    = _('Communicate with the Nokia Nokia 810 internet tablet.')

    PRODUCT_ID = [0x96]
    BCD        = [0x316]

    WINDOWS_MAIN_MEM = 'N810'

    MAIN_MEMORY_VOLUME_LABEL = 'N810 Main Memory'
