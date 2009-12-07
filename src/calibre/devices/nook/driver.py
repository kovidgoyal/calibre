# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Device driver for Barns and Nobel's Nook
'''

from calibre.devices.usbms.driver import USBMS

class NOOK(USBMS):

    name           = 'Nook Iliad Device Interface'
    description    = _('Communicate with the Barns and Noble Nook eBook reader.')
    author         = _('John Schember')
    supported_platforms = ['windows', 'linux']

    # Ordered list of supported formats
    # Be sure these have an entry in calibre.devices.mime
    FORMATS     = ['epub', 'pdb', 'pdf']

    VENDOR_ID   = [0x2080]
    PRODUCT_ID  = [0x001]
    BCD         = [0x322]

    VENDOR_NAME = 'B&N'
    WINDOWS_MAIN_MEM = 'NOOK'
    WINDOWS_CARD_A_MEM = 'NOOK'

    #OSX_MAIN_MEM = ''

    MAIN_MEMORY_VOLUME_LABEL  = 'BN Nook Main Memory'

    EBOOK_DIR_MAIN = 'my documents'
    SUPPORTS_SUB_DIRS = True

    def windows_sort_drives(self, drives):
        main = drives.get('main', None)
        card = drives.get('carda', None)
        if card and main and card < main:
            drives['main'] = card
            drives['carda'] = main

        return drives
