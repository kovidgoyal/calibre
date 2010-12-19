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
    FORMATS     = ['epub', 'pdf']

    VENDOR_ID   = {
            # HTC
            0x0bb4 : { 0x0c02 : [0x100, 0x0227, 0x0226], 0x0c01 : [0x100, 0x0227], 0x0ff9
                : [0x0100, 0x0227, 0x0226], 0x0c87: [0x0100, 0x0227, 0x0226],
                0xc92 : [0x100], 0xc97: [0x226]},

            # Eken
            0x040d : { 0x8510 : [0x0001] },

            # Motorola
            0x22b8 : { 0x41d9 : [0x216], 0x2d67 : [0x100], 0x41db : [0x216],
                0x4285 : [0x216], 0x42a3 : [0x216] },

            # Sony Ericsson
            0xfce : { 0xd12e : [0x0100]},

            # Google
            0x18d1 : { 0x4e11 : [0x0100, 0x226, 0x227], 0x4e12: [0x0100, 0x226,
                0x227]},

            # Samsung
            0x04e8 : { 0x681d : [0x0222, 0x0223, 0x0224, 0x0400],
                       0x681c : [0x0222, 0x0224, 0x0400],
                       0x6640 : [0x0100],
                     },

            # Acer
            0x502 : { 0x3203 : [0x0100]},

            # Dell
            0x413c : { 0xb007 : [0x0100, 0x0224]},

            # Eken?
            0x040d : { 0x0851 : [0x0001]},
            }
    EBOOK_DIR_MAIN = ['eBooks/import', 'wordplayer/calibretransfer', 'Books']
    EXTRA_CUSTOMIZATION_MESSAGE = _('Comma separated list of directories to '
            'send e-books to on the device. The first one that exists will '
            'be used')
    EXTRA_CUSTOMIZATION_DEFAULT = ', '.join(EBOOK_DIR_MAIN)

    VENDOR_NAME      = ['HTC', 'MOTOROLA', 'GOOGLE_', 'ANDROID', 'ACER',
            'GT-I5700', 'SAMSUNG', 'DELL', 'LINUX']
    WINDOWS_MAIN_MEM = ['ANDROID_PHONE', 'A855', 'A853', 'INC.NEXUS_ONE',
            '__UMS_COMPOSITE', '_MB200', 'MASS_STORAGE', '_-_CARD', 'SGH-I897',
            'GT-I9000', 'FILE-STOR_GADGET', 'SGH-T959', 'SAMSUNG_ANDROID',
            'SCH-I500_CARD', 'SPH-D700_CARD', 'MB810']
    WINDOWS_CARD_A_MEM = ['ANDROID_PHONE', 'GT-I9000_CARD', 'SGH-I897',
            'FILE-STOR_GADGET', 'SGH-T959', 'SAMSUNG_ANDROID']

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

    def get_main_ebook_dir(self, for_upload=False):
        dirs = self.EBOOK_DIR_MAIN
        if not for_upload:
            def aldiko_tweak(x):
                return 'eBooks' if x == 'eBooks/import' else x
            if isinstance(dirs, basestring):
                dirs = [dirs]
            dirs = list(map(aldiko_tweak, dirs))
        return dirs

class S60(USBMS):

    name = 'S60 driver'
    gui_name = 'S60 phone'
    description    = _('Communicate with S60 phones.')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']

    VENDOR_ID = [0x421]
    PRODUCT_ID = [0x156]
    BCD = [0x100]

    # For use with zxreader
    FORMATS = ['fb2']
    EBOOK_DIR_MAIN = 'FB2 Books'

    VENDOR_NAME = 'NOKIA'
    WINDOWS_MAIN_MEM = 'S60'
