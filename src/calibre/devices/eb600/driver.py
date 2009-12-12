# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Device driver for the Netronix EB600

Windows PNP strings:
 ('USBSTOR\\DISK&VEN_NETRONIX&PROD_EBOOK&REV_062E\\6&1A275569&0&EB6001009
2W00000&0', 2, u'F:\\')
        ('USBSTOR\\DISK&VEN_NETRONIX&PROD_EBOOK&REV_062E\\6&1A275569&0&EB6001009
2W00000&1', 3, u'G:\\')

'''

from calibre.devices.usbms.driver import USBMS

class EB600(USBMS):

    name           = 'Netronix EB600 Device Interface'
    description    = _('Communicate with the EB600 eBook reader.')
    author         = _('Kovid Goyal')
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'mobi', 'prc', 'chm', 'djvu', 'html', 'rtf', 'txt',
        'pdf']
    DRM_FORMATS = ['prc', 'mobi', 'html', 'pdf', 'txt']

    VENDOR_ID   = [0x1f85]
    PRODUCT_ID  = [0x1688]
    BCD         = [0x110]

    VENDOR_NAME      = 'NETRONIX'
    WINDOWS_MAIN_MEM = 'EBOOK'
    WINDOWS_CARD_A_MEM = 'EBOOK'

    OSX_MAIN_MEM = 'EB600 Internal Storage Media'
    OSX_CARD_A_MEM = 'EB600 Card Storage Media'

    MAIN_MEMORY_VOLUME_LABEL  = 'EB600 Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'EB600 Storage Card'

    EBOOK_DIR_MAIN = ''
    EBOOK_DIR_CARD_A = ''
    SUPPORTS_SUB_DIRS = True

    def windows_sort_drives(self, drives):
        main = drives.get('main', None)
        card = drives.get('carda', None)
        if card and main and card < main:
            drives['main'] = card
            drives['carda'] = main

        return drives


class COOL_ER(EB600):

    name = 'Cool-er device interface'
    gui_name = 'Cool-er'

    FORMATS = ['epub', 'mobi', 'prc', 'pdf', 'txt']

    VENDOR_NAME = 'COOL-ER'
    WINDOWS_MAIN_MEM = 'EREADER'

    OSX_MAIN_MEM = 'COOL-ER eReader Media'

    EBOOK_DIR_MAIN = 'my docs'

class SHINEBOOK(EB600):

    name = 'ShineBook device Interface'

    gui_name = 'ShineBook'

    FORMATS = ['epub', 'prc', 'rtf', 'pdf', 'txt']

    VENDOR_NAME      = 'LONGSHIN'
    WINDOWS_MAIN_MEM = 'ESHINEBOOK'

class POCKETBOOK360(EB600):

    name = 'PocketBook 360 Device Interface'

    gui_name = 'PocketBook 360'

    FORMATS = ['epub', 'fb2', 'prc', 'mobi', 'pdf', 'djvu', 'rtf', 'chm', 'txt']

    VENDOR_NAME = 'PHILIPS'
    WINDOWS_MAIN_MEM = 'MASS_STORGE'
    WINDOWS_CARD_A_MEM = 'MASS_STORGE'

    OSX_MAIN_MEM   = 'Philips Mass Storge Media'
    OSX_CARD_A_MEM = 'Philips Mass Storge Media'

