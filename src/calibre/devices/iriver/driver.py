#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re

from calibre.devices.usbms.driver import USBMS


class IRIVER_STORY(USBMS):

    name           = 'Iriver Story Device Interface'
    gui_name       = 'Iriver Story'
    description    = _('Communicate with the Iriver Story reader.')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'fb2', 'pdf', 'djvu', 'txt']

    VENDOR_ID   = [0x1006]
    PRODUCT_ID  = [0x4023, 0x4024, 0x4025, 0x4034, 0x4037]
    BCD         = [0x0323, 0x0326, 0x226]

    VENDOR_NAME = 'IRIVER'
    WINDOWS_MAIN_MEM = ['STORY', 'STORY_EB05', 'STORY_WI-FI', 'STORY_EB07',
                        'STORY_EB12']
    WINDOWS_MAIN_MEM = re.compile(r'(%s)&'%('|'.join(WINDOWS_MAIN_MEM)))
    WINDOWS_CARD_A_MEM = ['STORY', 'STORY_SD', 'STORY_EB12_SD']
    WINDOWS_CARD_A_MEM = re.compile(r'(%s)&'%('|'.join(WINDOWS_CARD_A_MEM)))

    # OSX_MAIN_MEM = 'Kindle Internal Storage Media'
    # OSX_CARD_A_MEM = 'Kindle Card Storage Media'

    MAIN_MEMORY_VOLUME_LABEL  = 'Story Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'Story Storage Card'
    EBOOK_DIR_MAIN = 'Book'

    SUPPORTS_SUB_DIRS = True
