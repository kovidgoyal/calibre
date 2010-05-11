# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from calibre.devices.usbms.driver import USBMS

class HTC_TD2(USBMS):

    name           = 'HTC TD2 Phone driver'
    gui_name       = 'HTC TD2'
    description    = _('Communicate with HTC TD2 phones.')
    author         = 'Charles Haley'
    supported_platforms = ['windows']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'pdf']

    VENDOR_ID   = {
            # HTC
            0x0bb4 : { 0x0c30 : [0x000]},
            }
    EBOOK_DIR_MAIN = ['EBooks']
    EXTRA_CUSTOMIZATION_MESSAGE = _('Comma separated list of directories to '
            'send e-books to on the device. The first one that exists will '
            'be used')
    EXTRA_CUSTOMIZATION_DEFAULT = ', '.join(EBOOK_DIR_MAIN)

    VENDOR_NAME      = ['']
    WINDOWS_MAIN_MEM = ['']

#    OSX_MAIN_MEM = 'HTC TD2 Phone Media'
#    MAIN_MEMORY_VOLUME_LABEL  = 'HTC Phone Internal Memory'

    SUPPORTS_SUB_DIRS = True

    def post_open_callback(self):
        opts = self.settings()
        dirs = opts.extra_customization
        if not dirs:
            dirs = self.EBOOK_DIR_MAIN
        else:
            dirs = [x.strip() for x in dirs.split(',')]
        self.EBOOK_DIR_MAIN = dirs
