# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.devices.usbms.driver import USBMS

class ANDROID(USBMS):

    name           = 'Android driver'
    gui_name       = 'Android phone'
    description    = _('Communicate with Android phones.')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub']

    VENDOR_ID   = [
            0x0bb4,
            ]
    PRODUCT_ID  = [0x0c02, 0x0c01]
    BCD         = [0x100]
    EBOOK_DIR_MAIN = ['wordplayer/calibretransfer', 'eBooks/import', 'Books']
    EXTRA_CUSTOMIZATION_MESSAGE = _('Comma separated list of directories to '
            'send e-books to on the device. The first one that exists will '
            'be used')
    EXTRA_CUSTOMIZATION_DEFAULT = ', '.join(EBOOK_DIR_MAIN)

    VENDOR_NAME      = 'HTC'
    WINDOWS_MAIN_MEM = 'ANDROID_PHONE'

    OSX_MAIN_MEM = 'HTC Android Phone Media'

    MAIN_MEMORY_VOLUME_LABEL  = 'Android Device Internal Memory'

    SUPPORTS_SUB_DIRS = True

    def get_main_ebook_dir(self):
        opts = self.settings()
        dirs = opts.extra_customization
        if not dirs:
            dirs = self.EBOOK_DIR_MAIN
        else:
            dirs = [x.strip() for x in dirs.split(',')]
        return dirs

