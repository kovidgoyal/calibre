# -*- coding: utf-8 -*-


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Device driver for the Nuut2
'''

from calibre.devices.usbms.driver import USBMS


class NUUT2(USBMS):

    name           = 'Nuut2 Device Interface'
    gui_name       = 'NeoLux Nuut2'
    description    = _('Communicate with the Nuut2 e-book reader.')
    author         = _('Kovid Goyal')
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'pdf', 'txt']
    DRM_FORMATS = ['epub']

    VENDOR_ID   = [0x140e]
    PRODUCT_ID  = [0xb055]
    BCD         = [0x318]

    VENDOR_NAME      = 'NEOLUX'
    WINDOWS_MAIN_MEM = 'NUUT2'

    OSX_MAIN_MEM = 'NEXTPPRS MASS STORAGE Media'

    MAIN_MEMORY_VOLUME_LABEL  = 'NUUT2 Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'NUUT2 Storage Card'

    EBOOK_DIR_MAIN = 'books'
    SUPPORTS_SUB_DIRS = True
