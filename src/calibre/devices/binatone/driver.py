# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Device driver for Bookeen's Cybook Gen 3
'''

from calibre.devices.usbms.driver import USBMS


class README(USBMS):

    name           = 'Binatone Readme Device Interface'
    gui_name       = 'Binatone Readme'
    description    = _('Communicate with the Binatone Readme e-book reader.')
    author         = 'John Schember'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    # Be sure these have an entry in calibre.devices.mime
    FORMATS     = ['txt']

    VENDOR_ID   = [0x04fc]
    PRODUCT_ID  = [0x5563]
    BCD         = [0x0100]

    VENDOR_NAME = ''
    WINDOWS_MAIN_MEM = 'MASS_STORAGE'
    WINDOWS_CARD_A_MEM = 'MASS_STORAGE'

    MAIN_MEMORY_VOLUME_LABEL  = 'Readme Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'Readme Storage Card'

    SUPPORTS_SUB_DIRS = True

    def linux_swap_drives(self, drives):
        if len(drives) < 2:
            return drives
        drives = list(drives)
        t = drives[0]
        drives[0] = drives[1]
        drives[1] = t
        return tuple(drives)

    def windows_sort_drives(self, drives):
        if len(drives) < 2:
            return drives
        main = drives.get('main', None)
        carda = drives.get('carda', None)
        if main and carda:
            drives['main'] = carda
            drives['carda'] = main
        return drives
