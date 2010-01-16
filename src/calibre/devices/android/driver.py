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

    VENDOR_ID   = {
            0x0bb4 : { 0x0c02 : [0x100], 0x0c01 : [0x100]},
            0x22b8 : { 0x41d9 : [0x216]},
            0x18d1 : { 0x4e11 : [0x0100]},
            }
    EBOOK_DIR_MAIN = ['wordplayer/calibretransfer', 'eBooks/import', 'Books']
    EXTRA_CUSTOMIZATION_MESSAGE = _('Comma separated list of directories to '
            'send e-books to on the device. The first one that exists will '
            'be used')
    EXTRA_CUSTOMIZATION_DEFAULT = ', '.join(EBOOK_DIR_MAIN)

    VENDOR_NAME      = ['HTC', 'MOTOROLA', 'GOOGLE_']
    WINDOWS_MAIN_MEM = ['ANDROID_PHONE', 'A855', 'INC.NEXUS_ONE']

    OSX_MAIN_MEM = 'HTC Android Phone Media'

    MAIN_MEMORY_VOLUME_LABEL  = 'Android Phone Internal Memory'

    SUPPORTS_SUB_DIRS = True

    def post_open_callback(self):
        opts = self.settings()
        dirs = opts.extra_customization
        if not dirs:
            dirs = self.EBOOK_DIR_MAIN
        else:
            dirs = [x.strip() for x in dirs.split(',')]
        self.EBOOK_DIR_MAIN = dirs

