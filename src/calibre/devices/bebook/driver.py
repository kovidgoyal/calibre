__license__   = 'GPL v3'
__copyright__ = '2009, Tijmen Ruizendaal <tijmen at mybebook.com>'

'''
Device driver for BeBook
'''

import re

from calibre.devices.usbms.driver import USBMS

class BEBOOK(USBMS):
    name           = 'BeBook driver'
    description    = _('Communicate with the BeBook eBook reader.')
    author         = _('Tijmen Ruizendaal')
    supported_platforms = ['windows', 'osx', 'linux']


    # Ordered list of supported formats
    FORMATS     = ['mobi', 'epub', 'pdf', 'txt']

    VENDOR_ID   = [0x0525]
    PRODUCT_ID  = [0x8803, 0x6803]
    BCD         = [0x312]

    VENDOR_NAME      = 'LINUX'
    WINDOWS_MAIN_MEM = 'FILE-STOR_GADGET'
    WINDOWS_CARD_A_MEM = 'FILE-STOR_GADGET'

    OSX_MAIN_MEM = 'Linux File-Stor Gadget Media'
    OSX_CARD_A_MEM = 'Linux File-Stor Gadget Media'

    MAIN_MEMORY_VOLUME_LABEL  = 'BeBook Internal Memory'
    STORAGE_CARD_VOLUME_LABEL = 'BeBook Storage Card'

    SUPPORTS_SUB_DIRS = True

    FDI_LUNS = {'lun0':1, 'lun1':0, 'lun2':2}

    def windows_sort_drives(self, drives):
        main = drives.get('main', None)
        card = drives.get('carda', None)
        if card and main and card < main:
            drives['main'] = card
            drives['carda'] = main

        return drives

    def osx_sort_names(self, names):
        main = names.get('main', None)
        card = names.get('carda', None)

        main_num = int(re.findall('\d+', main)[0]) if main else None
        card_num = int(re.findall('\d+', card)[0]) if card else None

        if card_num is not None and main_num is not None and card_num < main_num:
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


class BEBOOK_MINI(BEBOOK):
    name           = 'BeBook Mini driver'
    description    = _('Communicate with the BeBook Mini eBook reader.')


    VENDOR_ID	= [0x0492]
    PRODUCT_ID	= [0x8813]
    BCD         = [0x319]

    OSX_MAIN_MEM = 'BeBook Mini Internal Memory'
    OSX_CARD_MEM = 'BeBook Mini Storage Card'

    MAIN_MEMORY_VOLUME_LABEL  = 'BeBook Mini Internal Memory'
    STORAGE_CARD_VOLUME_LABEL = 'BeBook Mini Storage Card'

