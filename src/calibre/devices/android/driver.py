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
            0x0bb4 : { 0xc02 : [0x100, 0x0227, 0x0226, 0x222],
                       0xc01 : [0x100, 0x0227, 0x0226],
                       0xff9 : [0x0100, 0x0227, 0x0226],
                       0xc87 : [0x0100, 0x0227, 0x0226],
                       0xc91 : [0x0100, 0x0227, 0x0226],
                       0xc92  : [0x100, 0x0227, 0x0226, 0x222],
                       0xc97  : [0x100, 0x0227, 0x0226, 0x222],
                       0xc99  : [0x100, 0x0227, 0x0226, 0x222],
                       0xca2  : [0x100, 0x0227, 0x0226, 0x222],
                       0xca3  : [0x100, 0x0227, 0x0226, 0x222],
                       0xca4  : [0x100, 0x0227, 0x0226, 0x222],
            },

            # Eken
            0x040d : { 0x8510 : [0x0001], 0x0851 : [0x1] },

            # Motorola
            0x22b8 : { 0x41d9 : [0x216], 0x2d61 : [0x100], 0x2d67 : [0x100],
                       0x41db : [0x216], 0x4285 : [0x216], 0x42a3 : [0x216],
                       0x4286 : [0x216], 0x42b3 : [0x216], 0x42b4 : [0x216],
                       0x7086 : [0x0226], 0x70a8: [0x9999], 0x42c4 : [0x216],
                     },

            # Sony Ericsson
            0xfce : { 0xd12e : [0x0100]},

            # Google
            0x18d1 : {
                0x0001 : [0x0223],
                0x4e11 : [0x0100, 0x226, 0x227],
                0x4e12 : [0x0100, 0x226, 0x227],
                0x4e21 : [0x0100, 0x226, 0x227],
                0xb058 : [0x0222, 0x226, 0x227]
            },

            # Samsung
            0x04e8 : { 0x681d : [0x0222, 0x0223, 0x0224, 0x0400],
                       0x681c : [0x0222, 0x0224, 0x0400],
                       0x6640 : [0x0100],
                       0x685b : [0x0400],
                       0x685e : [0x0400],
                       0x6860 : [0x0400],
                       0x6877 : [0x0400],
                       0x689e : [0x0400],
                     },

            # Viewsonic
            0x0489 : { 0xc001 : [0x0226], 0xc004 : [0x0226], },

            # Acer
            0x502 : { 0x3203 : [0x0100, 0x224]},

            # Dell
            0x413c : { 0xb007 : [0x0100, 0x0224, 0x0226]},

            # LG
            0x1004 : { 0x61cc : [0x100], 0x61ce : [0x100], 0x618e : [0x226,
                0x9999] },

            # Archos
            0x0e79 : {
                0x1400 : [0x0222, 0x0216],
                0x1408 : [0x0222, 0x0216],
                0x1411 : [0x216],
                0x1417 : [0x0216],
                0x1419 : [0x0216],
                0x1420 : [0x0216],
                0x1422 : [0x0216]
            },

            # Huawei
            # Disabled as this USB id is used by various USB flash drives
            #0x45e : { 0x00e1 : [0x007], },

            # T-Mobile
            0x0408 : { 0x03ba : [0x0109], },

            # Xperia
            0x13d3 : { 0x3304 : [0x0001, 0x0002] },

            # CREEL?? Also Nextbook
            0x5e3 : { 0x726 : [0x222] },

            # ZTE
            0x19d2 : { 0x1353 : [0x226] },

            # Advent
            0x0955 : { 0x7100 : [0x9999] }, # This is the same as the Notion Ink Adam

            }
    EBOOK_DIR_MAIN = ['eBooks/import', 'wordplayer/calibretransfer', 'Books']
    EXTRA_CUSTOMIZATION_MESSAGE = _('Comma separated list of directories to '
            'send e-books to on the device. The first one that exists will '
            'be used')
    EXTRA_CUSTOMIZATION_DEFAULT = ', '.join(EBOOK_DIR_MAIN)

    VENDOR_NAME      = ['HTC', 'MOTOROLA', 'GOOGLE_', 'ANDROID', 'ACER',
            'GT-I5700', 'SAMSUNG', 'DELL', 'LINUX', 'GOOGLE', 'ARCHOS',
            'TELECHIP', 'HUAWEI', 'T-MOBILE', 'SEMC', 'LGE', 'NVIDIA',
            'GENERIC-', 'ZTE', 'MID']
    WINDOWS_MAIN_MEM = ['ANDROID_PHONE', 'A855', 'A853', 'INC.NEXUS_ONE',
            '__UMS_COMPOSITE', '_MB200', 'MASS_STORAGE', '_-_CARD', 'SGH-I897',
            'GT-I9000', 'FILE-STOR_GADGET', 'SGH-T959', 'SAMSUNG_ANDROID',
            'SCH-I500_CARD', 'SPH-D700_CARD', 'MB810', 'GT-P1000', 'DESIRE',
            'SGH-T849', '_MB300', 'A70S', 'S_ANDROID', 'A101IT', 'A70H',
            'IDEOS_TABLET', 'MYTOUCH_4G', 'UMS_COMPOSITE', 'SCH-I800_CARD',
            '7', 'A956', 'A955', 'A43', 'ANDROID_PLATFORM', 'TEGRA_2',
            'MB860', 'MULTI-CARD', 'MID7015A', 'INCREDIBLE', 'A7EB', 'STREAK',
            'MB525', 'ANDROID2.3', 'SGH-I997', 'GT-I5800_CARD', 'MB612',
            'GT-S5830_CARD', 'GT-S5570_CARD']
    WINDOWS_CARD_A_MEM = ['ANDROID_PHONE', 'GT-I9000_CARD', 'SGH-I897',
            'FILE-STOR_GADGET', 'SGH-T959', 'SAMSUNG_ANDROID', 'GT-P1000_CARD',
            'A70S', 'A101IT', '7', 'INCREDIBLE', 'A7EB', 'SGH-T849_CARD',
            '__UMS_COMPOSITE', 'SGH-I997_CARD']

    OSX_MAIN_MEM = 'Android Device Main Memory'

    MAIN_MEMORY_VOLUME_LABEL  = 'Android Device Main Memory'

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
