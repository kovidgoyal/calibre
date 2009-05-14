__license__   = 'GPL v3'
__copyright__ = '2009, Tijmen Ruizendaal <tijmen at mybebook.com>'
'''
Device driver for BeBook
'''

from calibre.devices.usbms.driver import USBMS

class BEBOOK(USBMS):
    name           = 'BeBook driver'
    description    = _('Communicate with the BeBook eBook reader.')
    author         = _('Tijmen Ruizendaal')
    supported_platforms = ['windows', 'osx', 'linux']


    # Ordered list of supported formats
    FORMATS     = ['mobi', 'epub', 'pdf', 'mobi', 'txt']

    VENDOR_ID   = [0x0525]
    PRODUCT_ID  = [0x8803, 0x6803]
    BCD         = [0x312]

    VENDOR_NAME      = 'LINUX'
    WINDOWS_MAIN_MEM = 'FILE-STOR_GADGET'
    WINDOWS_CARD_MEM = 'FILE-STOR_GADGET'

    OSX_MAIN_MEM = 'BeBook Internal Memory'
    OSX_CARD_A_MEM = 'BeBook Storage Card'

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

