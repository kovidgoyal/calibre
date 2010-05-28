#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.devices.usbms.driver import USBMS

class KOBO(USBMS):

    name = 'Kobo Reader Device Interface'
    gui_name = 'Kobo Reader'
    description = _('Communicate with the Kobo Reader')
    author = 'Kovid Goyal'

    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'pdf']

    VENDOR_ID   = [0x2237]
    PRODUCT_ID  = [0x4161]
    BCD         = [0x0110]

    VENDOR_NAME = 'KOBO_INC'
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = '.KOBOEREADER'

    EBOOK_DIR_MAIN = ''
    SUPPORTS_SUB_DIRS = True

