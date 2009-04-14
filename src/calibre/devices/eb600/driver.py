__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
'''
Device driver for the Netronix EB600
'''

from calibre.devices.usbms.driver import USBMS

class EB600(USBMS):
    # Ordered list of supported formats
    FORMATS     = ['epub', 'prc', 'chm', 'djvu', 'html', 'rtf', 'txt', 'pdf']
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
        main = drives['main']
        card = drives['carda']
        if card and main and card < main:
            drives['main'] = card
            drives['carda'] = main

        return drives


