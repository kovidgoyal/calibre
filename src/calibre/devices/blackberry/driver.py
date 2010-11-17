# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.devices.usbms.driver import USBMS

class BLACKBERRY(USBMS):

    name           = 'Blackberry Device Interface'
    gui_name       = 'Blackberry'
    description    = _('Communicate with the Blackberry smart phone.')
    author         = _('Kovid Goyal')
    supported_platforms = ['windows', 'linux', 'osx']

    # Ordered list of supported formats
    FORMATS     = ['mobi', 'prc']

    VENDOR_ID   = [0x0fca]
    PRODUCT_ID  = [0x8004, 0x0004]
    BCD         = [0x0200, 0x0107, 0x0210, 0x0201, 0x0211]

    VENDOR_NAME = 'RIM'
    WINDOWS_MAIN_MEM = 'BLACKBERRY_SD'

    MAIN_MEMORY_VOLUME_LABEL  = 'Blackberry SD Card'

    EBOOK_DIR_MAIN = 'eBooks'
    SUPPORTS_SUB_DIRS = True
