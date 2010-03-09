# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, Tijmen Ruizendaal <tijmen at mybebook.com>'
__docformat__ = 'restructuredtext en'

'''
Device driver for Hanlin
'''

import re

from calibre.devices.usbms.driver import USBMS

class HANLINV3(USBMS):

    name           = 'Hanlin V3 driver'
    gui_name       = 'Hanlin V3'
    description    = _('Communicate with Hanlin V3 eBook readers.')
    author         = 'Tijmen Ruizendaal'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'mobi', 'fb2', 'lit', 'prc', 'pdf', 'rtf', 'txt']

    VENDOR_ID   = [0x0525]
    PRODUCT_ID  = [0x8803, 0x6803]
    BCD         = [0x312]

    VENDOR_NAME      = 'LINUX'
    WINDOWS_MAIN_MEM = 'FILE-STOR_GADGET'
    WINDOWS_CARD_A_MEM = 'FILE-STOR_GADGET'

    OSX_MAIN_MEM = 'Linux File-Stor Gadget Media'
    OSX_CARD_A_MEM = 'Linux File-Stor Gadget Media'

    MAIN_MEMORY_VOLUME_LABEL  = 'Hanlin V3 Internal Memory'
    STORAGE_CARD_VOLUME_LABEL = 'Hanlin V3 Storage Card'

    SUPPORTS_SUB_DIRS = True

    def windows_sort_drives(self, drives):
        main = drives.get('main', None)
        card = drives.get('carda', None)
        if card and main and card > main:
            drives['main'] = card
            drives['carda'] = main

        if card and not main:
            drives['main'] = card
            drives['carda'] = None

        return drives

    def windows_open_callback(self, drives):
        if 'main' not in drives and 'carda' in drives:
            drives['main'] = drives.pop('carda')
        return drives

    def osx_sort_names(self, names):
        main = names.get('main', None)
        card = names.get('carda', None)

        try:
            main_num = int(re.findall('\d+', main)[0]) if main else None
        except:
            main_num = None
        try:
            card_num = int(re.findall('\d+', card)[0]) if card else None
        except:
            card_num = None

        if card_num is not None and main_num is not None and card_num > main_num:
            names['main'] = card
            names['carda'] = main

        if card and not main:
            names['main'] = card
            names['carda'] = None

        return names

    def linux_swap_drives(self, drives):
        if len(drives) < 2: return drives
        drives = list(drives)
        t = drives[0]
        drives[0] = drives[1]
        drives[1] = t
        return tuple(drives)


class HANLINV5(HANLINV3):
    name           = 'Hanlin V5 driver'
    gui_name       = 'Hanlin V5'
    description    = _('Communicate with Hanlin V5 eBook readers.')


    VENDOR_ID	= [0x0492]
    PRODUCT_ID	= [0x8813]
    BCD         = [0x319]

    OSX_MAIN_MEM = 'Hanlin V5 Internal Memory'
    OSX_CARD_MEM = 'Hanlin V5 Storage Card'

    MAIN_MEMORY_VOLUME_LABEL  = 'Hanlin V5 Internal Memory'
    STORAGE_CARD_VOLUME_LABEL = 'Hanlin V5 Storage Card'


class BOOX(HANLINV3):

    name           = 'BOOX driver'
    gui_name       = 'BOOX'
    description    = _('Communicate with the BOOX eBook reader.')
    author         = 'Jesus Manuel Marinho Valcarce'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'fb2', 'djvu', 'pdf', 'html', 'txt', 'rtf', 'mobi', 'prc', 'chm']

    VENDOR_ID   = [0x0525]
    PRODUCT_ID  = [0xa4a5]
    BCD         = [0x322]

    MAIN_MEMORY_VOLUME_LABEL  = 'BOOX Internal Memory'
    STORAGE_CARD_VOLUME_LABEL = 'BOOX Storage Card'

    EBOOK_DIR_MAIN = 'MyBooks'
    EBOOK_DIR_CARD_A = 'MyBooks'


    def windows_sort_drives(self, drives):
        main = drives.get('main', None)
        card = drives.get('carda', None)
        if card and main and card < main:
            drives['main'] = card
            drives['carda'] = main

        return drives


