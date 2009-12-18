#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.devices.usbms.driver import USBMS

class ESLICK(USBMS):

    name           = 'ESlick Device Interface'
    gui_name       = 'Foxit ESlick'
    description    = _('Communicate with the ESlick eBook reader.')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'pdb', 'pdf', 'txt']

    VENDOR_ID   = [0x04cc]
    PRODUCT_ID  = [0x1a64]
    BCD         = [0x0110]

    VENDOR_NAME = 'FOXIT'
    WINDOWS_MAIN_MEM = 'ESLICK_USB_DEVIC'
    WINDOWS_CARD_A_MEM = 'ESLICK_USB_DEVIC'

    #OSX_MAIN_MEM = 'Kindle Internal Storage Media'
    #OSX_CARD_A_MEM = 'Kindle Card Storage Media'

    MAIN_MEMORY_VOLUME_LABEL  = 'ESlick Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'ESlick Storage Card'

    SUPPORTS_SUB_DIRS = True

    def windows_sort_drives(self, drives):
        main = drives.get('main', None)
        card = drives.get('carda', None)
        if card and main and card < main:
            drives['main'] = card
            drives['carda'] = main

        return drives

