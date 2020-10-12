# -*- coding: utf-8 -*-


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import io
import os

from calibre import fsync
from calibre.devices.usbms.driver import USBMS
from polyglot.builtins import string_or_bytes

HTC_BCDS = [0x100, 0x0222, 0x0224, 0x0226, 0x227, 0x228, 0x229, 0x0231, 0x9999]


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
            0x0bb4 : {0xc02  : HTC_BCDS,
                       0xc01  : HTC_BCDS,
                       0xff9  : HTC_BCDS,
                       0xc86  : HTC_BCDS,
                       0xc87  : HTC_BCDS,
                       0xc8d  : HTC_BCDS,
                       0xc91  : HTC_BCDS,
                       0xc92  : HTC_BCDS,
                       0xc97  : HTC_BCDS,
                       0xc99  : HTC_BCDS,
                       0xca2  : HTC_BCDS,
                       0xca3  : HTC_BCDS,
                       0xca4  : HTC_BCDS,
                       0xca9  : HTC_BCDS,
                       0xcac  : HTC_BCDS,
                       0xcba  : HTC_BCDS,
                       0xccf  : HTC_BCDS,
                       0xcd6  : HTC_BCDS,
                       0xce5  : HTC_BCDS,
                       0xcec  : HTC_BCDS,
                       0x0cf5 : HTC_BCDS,
                       0x2910 : HTC_BCDS,
                       0xe77  : HTC_BCDS,
                       0xff9  : HTC_BCDS,
                       0x0001 : [0x255],
            },

            # Eken
            0x040d : {0x8510 : [0x0001], 0x0851 : [0x1]},

            # Trekstor
            0x1e68 : {
                0x006a : [0x0231],
                0x0062 : [0x222],  # Surftab ventos https://bugs.launchpad.net/bugs/1204885
            },

            # Motorola
            0x22b8 : {
                0x41d9 : [0x216], 0x2d61 : [0x100], 0x2d67 : [0x100],
                0x2de8 : [0x229],
                0x41db : [0x216], 0x4285 : [0x216], 0x42a3 : [0x216],
                0x4286 : [0x216], 0x42b3 : [0x216], 0x42b4 : [0x216],
                0x7086 : [0x0226], 0x70a8: [0x9999], 0x42c4 : [0x216],
                0x70c6 : [0x226], 0x70c7: [0x226],
                0x4316 : [0x216],
                0x4317 : [0x216],
                0x42d6 : [0x216],
                0x42d7 : [0x216],
                0x42f7 : [0x216],
                0x4365 : [0x216],
                0x4366 : [0x216],
                0x4371 : [0x216],
            },
            # Freescale
            0x15a2 : {
                0x0c01 : [0x226]
            },

            # Alcatel
            0x05c6 : {
                0x9018 : [0x0226],
            },

            # Sony Ericsson
            0xfce : {
                0xa173 : [0x216],
                0xd12e : [0x0100],
                0xe156 : [0x226],
                0xe15d : [0x226],
                0xe14f : [0x0226],
                0x614f : [0x0226, 0x100],
                0x6156 : [0x0226, 0x100],
                },

            # Google
            0x18d1 : {
                0x0001 : [0x0222, 0x0223, 0x230, 0x255, 0x9999],
                0x0002 : [0x9999],
                0x0003 : [0x0230, 0x9999],
                0x4e11 : [0x0100, 0x226, 0x227],
                0x4e12 : [0x0100, 0x226, 0x227],
                0x4e21 : [0x0100, 0x226, 0x227, 0x231],
                0x4e22 : [0x0100, 0x226, 0x227, 0x231],
                0xb058 : [0x0222, 0x226, 0x227],
                0x0ff9 : [0x0226],
                0xc91  : HTC_BCDS,
                0xdddd : [0x216],
                0x0d01 : [0x9999],
                0x0d02 : [0x9999],
                0x2d01 : [0x9999],
                0xdeed : [0x231, 0x226],
            },

            # Samsung
            0x04e8 : {0x681d : [0x0222, 0x0223, 0x0224, 0x0400],
                       0x681c : [0x0222, 0x0223, 0x0224, 0x0400],
                       0x6640 : [0x0100],
                       0x685b : [0x0400, 0x0226],
                       0x685e : [0x0400, 0x226],
                       0x6860 : [0x0400],
                       0x6863 : [0x226],
                       0x6877 : [0x0400],
                       0x689e : [0x0400],
                       0xdeed : [0x0222],
                       0x1234 : [0x0400],
                     },

            # Viewsonic/Vizio
            0x0489 : {
                    0xc000 : [0x0226],
                    0xc001 : [0x0226],
                    0xc004 : [0x0226],
                    0x8801 : [0x0226, 0x0227],
                    0xe115 : [0x0216],  # PocketBook A10
            },

            # Another Viewsonic
            0x0bb0 : {
                    0x2a2b : [0x0226, 0x0227],
            },

            # Acer
            0x502 : {0x3203 : [0x0100, 0x224]},

            # Dell
            0x413c : {0xb007 : [0x0100, 0x0224, 0x0226]},

            # LG
            0x1004 : {
                    0x61c5 : [0x100, 0x226, 0x227, 0x229, 0x9999],
                    0x61cc : [0x226, 0x227, 0x9999, 0x100],
                    0x61ce : [0x226, 0x227, 0x9999, 0x100],
                    0x618e : [0x226, 0x227, 0x9999, 0x100],
                    0x6205 : [0x226, 0x227, 0x9999, 0x100],
                    0x6234 : [0x231],
                    },

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
            # 0x45e : { 0x00e1 : [0x007], },

            # T-Mobile
            0x0408 : {0x03ba : [0x0109], },

            # Xperia
            0x13d3 : {0x3304 : [0x0001, 0x0002]},

            # ZTE
            0x19d2 : {0x1353 : [0x226], 0x1351 : [0x227]},

            # Advent
            0x0955 : {0x7100 : [0x9999]},  # This is the same as the Notion Ink Adam

            # Kobo
            0x2237: {0x2208 : [0x0226]},

            # Lenovo
            0x17ef : {
                    0x7421 : [0x0216],
                    0x741b : [0x9999],
                    0x7640 : [0x0255],
            },

            # Pantech
            0x10a9 : {0x6050 : [0x227]},

            # Prestigio and Teclast
            0x2207 : {0 : [0x222], 0x10 : [0x222]},

            # OPPO
            0x22d9 : {0x2768: [0x228]},

            }
    EBOOK_DIR_MAIN = ['eBooks/import', 'wordplayer/calibretransfer', 'Books',
            'sdcard/ebooks']
    EXTRA_CUSTOMIZATION_MESSAGE = [_('Comma separated list of directories to '
            'send e-books to on the device\'s <b>main memory</b>. The first one that exists will '
            'be used'),
            _('Comma separated list of directories to '
            'send e-books to on the device\'s <b>storage cards</b>. The first one that exists will '
            'be used')
            ]

    EXTRA_CUSTOMIZATION_DEFAULT = [', '.join(EBOOK_DIR_MAIN), '']

    VENDOR_NAME      = ['HTC', 'MOTOROLA', 'GOOGLE_', 'ANDROID', 'ACER',
            'GT-I5700', 'SAMSUNG', 'DELL', 'LINUX', 'GOOGLE', 'ARCHOS',
            'TELECHIP', 'HUAWEI', 'T-MOBILE', 'SEMC', 'LGE', 'NVIDIA',
            'GENERIC-', 'ZTE', 'MID', 'QUALCOMM', 'PANDIGIT', 'HYSTON',
            'VIZIO', 'GOOGLE', 'FREESCAL', 'KOBO_INC', 'LENOVO', 'ROCKCHIP',
            'POCKET', 'ONDA_MID', 'ZENITHIN', 'INGENIC', 'PMID701C', 'PD',
            'PMP5097C', 'MASS', 'NOVO7', 'ZEKI', 'COBY', 'SXZ', 'USB_2.0',
            'COBY_MID', 'VS', 'AINOL', 'TOPWISE', 'PAD703', 'NEXT8D12',
            'MEDIATEK', 'KEENHI', 'TECLAST', 'SURFTAB', 'XENTA', 'OBREEY_S',
            'SURFTAB_', 'ONYX-INT', 'IMCOSYS', 'SURFPAD3', 'GRAMMATA',
    ]
    WINDOWS_MAIN_MEM = ['ANDROID_PHONE', 'A855', 'A853', 'A953', 'INC.NEXUS_ONE',
            '__UMS_COMPOSITE', '_MB200', 'MASS_STORAGE', '_-_CARD', 'SGH-I897',
            'GT-I9000', 'FILE-STOR_GADGET', 'SGH-T959_CARD', 'SGH-T959', 'SAMSUNG_ANDROID',
            'SCH-I500_CARD', 'SPH-D700_CARD', 'MB810', 'GT-P1000', 'DESIRE',
            'SGH-T849', '_MB300', 'A70S', 'S_ANDROID', 'A101IT', 'A70H',
            'IDEOS_TABLET', 'MYTOUCH_4G', 'UMS_COMPOSITE', 'SCH-I800_CARD',
            '7', 'A956', 'A955', 'A43', 'ANDROID_PLATFORM', 'TEGRA_2',
            'MB860', 'MULTI-CARD', 'MID7015A', 'INCREDIBLE', 'A7EB', 'STREAK',
            'MB525', 'ANDROID2.3', 'SGH-I997', 'GT-I5800_CARD', 'MB612',
            'GT-S5830_CARD', 'GT-S5570_CARD', 'MB870', 'MID7015A',
            'ALPANDIGITAL', 'ANDROID_MID', 'VTAB1008', 'EMX51_BBG_ANDROI',
            'UMS', '.K080', 'P990', 'LTE', 'MB853', 'GT-S5660_CARD', 'A107',
            'GT-I9003_CARD', 'XT912', 'FILE-CD_GADGET', 'RK29_SDK', 'MB855',
            'XT910', 'BOOK_A10', 'USB_2.0_DRIVER', 'I9100T', 'P999DW',
            'KTABLET_PC', 'INGENIC', 'GT-I9001_CARD', 'USB_2.0',
            'GT-S5830L_CARD', 'UNIVERSE', 'XT875', 'PRO', '.KOBO_VOX',
            'THINKPAD_TABLET', 'SGH-T989', 'YP-G70', 'STORAGE_DEVICE',
            'ADVANCED', 'SGH-I727', 'USB_FLASH_DRIVER', 'ANDROID',
            'S5830I_CARD', 'MID7042', 'LINK-CREATE', '7035', 'VIEWPAD_7E',
            'NOVO7', 'MB526', '_USB#WYK7MSF8KE', 'TABLET_PC', 'F', 'MT65XX_MS',
            'ICS', 'E400', '__FILE-STOR_GADG', 'ST80208-1', 'GT-S5660M_CARD', 'XT894', '_USB',
            'PROD_TAB13-201', 'URFPAD2', 'MID1126', 'ST10216-1', 'S5360L_CARD', 'IDEATAB_A1000-F',
            'LBOOX', 'LTAGUS', 'IMCOV6L', '_101', 'LPAPYRE_624', 'S.L.',
    ]
    WINDOWS_CARD_A_MEM = ['ANDROID_PHONE', 'GT-I9000_CARD', 'SGH-I897',
            'FILE-STOR_GADGET', 'SGH-T959_CARD', 'SGH-T959', 'SAMSUNG_ANDROID', 'GT-P1000_CARD',
            'A70S', 'A101IT', '7', 'INCREDIBLE', 'A7EB', 'SGH-T849_CARD',
            '__UMS_COMPOSITE', 'SGH-I997_CARD', 'MB870', 'ALPANDIGITAL',
            'ANDROID_MID', 'P990_SD_CARD', '.K080', 'LTE_CARD', 'MB853',
            'A1-07___C0541A4F', 'XT912', 'MB855', 'XT910', 'BOOK_A10_CARD',
            'USB_2.0_DRIVER', 'I9100T', 'P999DW_SD_CARD', 'KTABLET_PC',
            'FILE-CD_GADGET', 'GT-I9001_CARD', 'USB_2.0', 'XT875',
            'UMS_COMPOSITE', 'PRO', '.KOBO_VOX', 'SGH-T989_CARD', 'SGH-I727',
            'USB_FLASH_DRIVER', 'ANDROID', 'MID7042', '7035', 'VIEWPAD_7E',
            'NOVO7', 'ADVANCED', 'TABLET_PC', 'F', 'E400_SD_CARD', 'ST80208-1', 'XT894',
            '_USB', 'PROD_TAB13-201', 'URFPAD2', 'MID1126', 'ANDROID_PLATFORM',
            'ST10216-1', 'LBOOX', 'LTAGUS', 'IMCOV6L',
    ]

    OSX_MAIN_MEM = 'Android Device Main Memory'

    MAIN_MEMORY_VOLUME_LABEL  = 'Android Device Main Memory'

    SUPPORTS_SUB_DIRS = True

    def post_open_callback(self):
        opts = self.settings()
        opts = opts.extra_customization
        if not opts:
            opts = [self.EBOOK_DIR_MAIN, '']

        def strtolist(x):
            if isinstance(x, string_or_bytes):
                x = [y.strip() for y in x.split(',')]
            return x or []

        opts = [strtolist(x) for x in opts]
        self._android_main_ebook_dir = opts[0]
        self._android_card_ebook_dir = opts[1]

    def get_main_ebook_dir(self, for_upload=False):
        dirs = self._android_main_ebook_dir
        if not for_upload:
            def aldiko_tweak(x):
                return 'eBooks' if x == 'eBooks/import' else x
            dirs = list(map(aldiko_tweak, dirs))
        return dirs

    def get_carda_ebook_dir(self, for_upload=False):
        if not for_upload:
            return ''
        return self._android_card_ebook_dir

    def get_cardb_ebook_dir(self, for_upload=False):
        return self.get_carda_ebook_dir()

    def windows_sort_drives(self, drives):
        try:
            vid, pid, bcd = self.device_being_opened[:3]
        except:
            vid, pid, bcd = -1, -1, -1
        if (vid, pid, bcd) == (0x0e79, 0x1408, 0x0222):
            letter_a = drives.get('carda', None)
            if letter_a is not None:
                drives['carda'] = drives['main']
                drives['main']  = letter_a
        return drives

    @classmethod
    def configure_for_kindle_app(cls):
        proxy = cls._configProxy()
        proxy['format_map'] = ['azw3', 'mobi', 'azw', 'azw1', 'azw4', 'pdf']
        proxy['use_subdirs'] = False
        proxy['extra_customization'] = [
                ','.join(['kindle']+cls.EBOOK_DIR_MAIN), '']

    @classmethod
    def configure_for_generic_epub_app(cls):
        proxy = cls._configProxy()
        del proxy['format_map']
        del proxy['use_subdirs']
        del proxy['extra_customization']


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


class WEBOS(USBMS):

    name           = 'WebOS driver'
    gui_name       = 'WebOS Tablet'
    description    = _('Communicate with WebOS tablets.')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['mobi', 'azw', 'prc']

    VENDOR_ID   = [0x0830]
    PRODUCT_ID  = [0x8074, 0x8072]
    BCD         = [0x0327]

    EBOOK_DIR_MAIN = '.palmkindle'
    VENDOR_NAME = 'HP'
    WINDOWS_MAIN_MEM = 'WEBOS-DEVICE'

    THUMBNAIL_HEIGHT = 160
    THUMBNAIL_WIDTH = 120

    def upload_cover(self, path, filename, metadata, filepath):

        from PIL import Image, ImageDraw

        coverdata = getattr(metadata, 'thumbnail', None)
        if coverdata and coverdata[2]:
            cover = Image.open(io.BytesIO(coverdata[2]))
        else:
            coverdata = lopen(I('library.png'), 'rb').read()

            cover = Image.new('RGB', (120,160), 'black')
            im = Image.open(io.BytesIO(coverdata))
            im.thumbnail((120, 160), Image.ANTIALIAS)

            x, y = im.size
            cover.paste(im, ((120-x)/2, (160-y)/2))

            draw = ImageDraw.Draw(cover)
            draw.text((1, 10), metadata.get('title', _('Unknown')).encode('ascii', 'ignore'))
            draw.text((1, 140), metadata.get('authors', _('Unknown'))[0].encode('ascii', 'ignore'))

        data = io.BytesIO()
        cover.save(data, 'JPEG')
        coverdata = data.getvalue()

        with lopen(os.path.join(path, 'coverCache', filename + '-medium.jpg'), 'wb') as coverfile:
            coverfile.write(coverdata)
            fsync(coverfile)

        coverdata = getattr(metadata, 'thumbnail', None)
        if coverdata and coverdata[2]:
            cover = Image.open(io.BytesIO(coverdata[2]))
        else:
            coverdata = lopen(I('library.png'), 'rb').read()

            cover = Image.new('RGB', (52,69), 'black')
            im = Image.open(io.BytesIO(coverdata))
            im.thumbnail((52, 69), Image.ANTIALIAS)

            x, y = im.size
            cover.paste(im, ((52-x)//2, (69-y)//2))

        cover2 = cover.resize((52, 69), Image.ANTIALIAS).convert('RGB')

        data = io.BytesIO()
        cover2.save(data, 'JPEG')
        coverdata = data.getvalue()

        with lopen(os.path.join(path, 'coverCache', filename + '-small.jpg'), 'wb') as coverfile:
            coverfile.write(coverdata)
            fsync(coverfile)
