# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Device driver for the Netronix EB600

Windows PNP strings:
 ('USBSTOR\\DISK&VEN_NETRONIX&PROD_EBOOK&REV_062E\\6&1A275569&0&EB6001009
2W00000&0', 2, u'F:\\')
        ('USBSTOR\\DISK&VEN_NETRONIX&PROD_EBOOK&REV_062E\\6&1A275569&0&EB6001009
2W00000&1', 3, u'G:\\')

'''
import re

from calibre.devices.usbms.driver import USBMS


class EB600(USBMS):

    name           = 'Netronix EB600 Device Interface'
    gui_name       = 'Netronix EB600'
    description    = _('Communicate with the EB600 e-book reader.')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'mobi', 'prc', 'chm', 'djvu', 'html', 'rtf', 'txt',
        'pdf']
    DRM_FORMATS = ['prc', 'mobi', 'html', 'pdf', 'txt']

    VENDOR_ID   = [0x1f85]
    PRODUCT_ID  = [0x1688]
    BCD         = [0x110]

    VENDOR_NAME      = ['NETRONIX', 'WOLDER', 'MD86371']
    WINDOWS_MAIN_MEM = ['EBOOK', 'MIBUK_GAMMA_6.2', 'MD86371']
    WINDOWS_CARD_A_MEM = ['EBOOK', 'MD86371']

    OSX_MAIN_MEM = 'EB600 Internal Storage Media'
    OSX_CARD_A_MEM = 'EB600 Card Storage Media'

    MAIN_MEMORY_VOLUME_LABEL  = 'EB600 Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'EB600 Storage Card'

    EBOOK_DIR_MAIN = ''
    EBOOK_DIR_CARD_A = ''
    SUPPORTS_SUB_DIRS = True


class TOLINO(EB600):

    name = 'Tolino Shine Device Interface'
    gui_name = 'tolino shine'
    description    = _('Communicate with the tolino shine and vision readers')
    FORMATS = ['epub', 'pdf', 'txt']
    PRODUCT_ID  = EB600.PRODUCT_ID + [0x6033, 0x6052, 0x6053]
    BCD         = [0x226, 0x9999]
    VENDOR_NAME      = ['DEUTSCHE', 'LINUX']
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = ['_TELEKOMTOLINO', 'FILE-CD_GADGET']

    EXTRA_CUSTOMIZATION_MESSAGE = [
        _('Swap main and card A') +
        ':::' +
        _('Check this box if the device\'s main memory is being seen as card a and the card '
            'is being seen as main memory. Some tolino devices may need this option.'),
    ]

    EXTRA_CUSTOMIZATION_DEFAULT = [
        True,
    ]

    OPT_SWAP_MEMORY = 0

    # There are apparently two versions of this device, one with swapped
    # drives and one without, see https://bugs.launchpad.net/bugs/1240504
    def linux_swap_drives(self, drives):
        e = self.settings().extra_customization
        if len(drives) < 2 or not drives[0] or not drives[1] or not e[self.OPT_SWAP_MEMORY]:
            return drives
        drives = list(drives)
        t = drives[0]
        drives[0] = drives[1]
        drives[1] = t
        return tuple(drives)

    def windows_sort_drives(self, drives):
        e = self.settings().extra_customization
        if len(drives) < 2 or not e[self.OPT_SWAP_MEMORY]:
            return drives
        main = drives.get('main', None)
        carda = drives.get('carda', None)
        if main and carda:
            drives['main'] = carda
            drives['carda'] = main
        return drives

    def osx_sort_names(self, names):
        e = self.settings().extra_customization
        if len(names) < 2 or not e[self.OPT_SWAP_MEMORY]:
            return names
        main = names.get('main', None)
        card = names.get('carda', None)

        if main is not None and card is not None:
            names['main'] = card
            names['carda'] = main

        return names

    def post_open_callback(self):
        # The tolino vision only handles books inside the Books folder
        product_id, bcd = self.device_being_opened[1], self.device_being_opened[2]
        is_tolino = product_id in (0x6033, 0x6052, 0x6053) or (product_id == 0x1688 and bcd == 0x226)
        self.ebook_dir_for_upload = 'Books' if is_tolino else ''

    def get_main_ebook_dir(self, for_upload=False):
        if for_upload:
            return getattr(self, 'ebook_dir_for_upload', self.EBOOK_DIR_MAIN)
        return self.EBOOK_DIR_MAIN


class COOL_ER(EB600):

    name = 'Cool-er device interface'
    gui_name = 'Cool-er'

    FORMATS = ['epub', 'mobi', 'prc', 'pdf', 'txt']

    VENDOR_NAME = 'COOL-ER'
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = 'EREADER'

    OSX_MAIN_MEM = 'COOL-ER eReader Media'

    EBOOK_DIR_MAIN = 'my docs'


class SHINEBOOK(EB600):

    name = 'ShineBook device Interface'

    gui_name = 'ShineBook'

    FORMATS = ['epub', 'prc', 'rtf', 'pdf', 'txt']

    VENDOR_NAME      = 'LONGSHIN'
    WINDOWS_MAIN_MEM = 'ESHINEBOOK'
    MAIN_MEMORY_VOLUME_LABEL  = 'ShineBook Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'ShineBook Storage Card'

    @classmethod
    def can_handle(cls, dev, debug=False):
        return dev[4] == 'ShineBook'


class POCKETBOOK360(EB600):

    # Device info on OS X
    # (8069L, 5768L, 272L, u'', u'', u'1.00')

    name = 'PocketBook 360 Device Interface'

    gui_name = 'PocketBook 360'
    VENDOR_ID   = [0x1f85, 0x525]
    PRODUCT_ID  = [0x1688, 0xa4a5]
    BCD         = [0x110]

    FORMATS = ['epub', 'fb2', 'prc', 'mobi', 'pdf', 'djvu', 'rtf', 'chm', 'txt']

    VENDOR_NAME = ['PHILIPS', '__POCKET', 'POCKETBO']
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = ['MASS_STORGE', 'BOOK_USB_STORAGE',
            'OK_POCKET_611_61', 'OK_POCKET_360+61']

    OSX_MAIN_MEM = OSX_CARD_A_MEM = 'Philips Mass Storge Media'
    OSX_MAIN_MEM_VOL_PAT = re.compile(r'/Pocket')

    @classmethod
    def can_handle(cls, dev, debug=False):
        return dev[-1] == '1.00' and not dev[-2] and not dev[-3]


class POCKETBOOKHD(EB600):

    name = 'Pocket Touch HD Device Interface'
    gui_name = 'PocketBook HD'
    PRODUCT_ID  = [0x6a42]
    BCD         = [0x9999]
    FORMATS = ['epub', 'fb2', 'prc', 'mobi', 'docx', 'doc', 'pdf', 'djvu', 'rtf', 'chm', 'txt']


class GER2(EB600):

    name = 'Ganaxa GeR2 Device Interface'
    gui_name = 'Ganaxa GeR2'

    FORMATS = ['pdf']

    VENDOR_ID   = [0x3034]
    PRODUCT_ID  = [0x1795]
    BCD         = [0x132]

    VENDOR_NAME = 'GANAXA'
    WINDOWS_MAIN_MEN = 'GER2_________-FD'
    WINDOWS_CARD_A_MEM = 'GER2_________-SD'


class ITALICA(EB600):

    name = 'Italica Device Interface'
    gui_name = 'Italica'
    icon = I('devices/italica.png')

    FORMATS = ['epub', 'rtf', 'fb2', 'html', 'prc', 'mobi', 'pdf', 'txt']

    VENDOR_NAME = 'ITALICA'
    WINDOWS_MAIN_MEM = 'EREADER'
    WINDOWS_CARD_A_MEM = WINDOWS_MAIN_MEM

    OSX_MAIN_MEM = 'Italica eReader Media'
    OSX_CARD_A_MEM = OSX_MAIN_MEM

    MAIN_MEMORY_VOLUME_LABEL  = 'Italica Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'Italica Storage Card'


class ECLICTO(EB600):

    name = 'eClicto Device Interface'
    gui_name = 'eClicto'

    FORMATS = ['epub', 'pdf', 'htm', 'html', 'txt']

    VENDOR_NAME = 'ECLICTO'
    WINDOWS_MAIN_MEM = 'EBOOK'
    WINDOWS_CARD_A_MEM = 'EBOOK'

    EBOOK_DIR_MAIN = 'Text'
    EBOOK_DIR_CARD_A = ''


class DBOOK(EB600):

    name = 'Airis Dbook Device Interface'
    gui_name = 'Airis Dbook'

    FORMATS = ['epub', 'mobi', 'prc', 'fb2', 'html', 'pdf', 'rtf', 'txt']

    VENDOR_NAME = 'INFINITY'
    WINDOWS_MAIN_MEM = 'AIRIS_DBOOK'
    WINDOWS_CARD_A_MEM = 'AIRIS_DBOOK'


class INVESBOOK(EB600):

    name = 'Inves Book Device Interface'
    gui_name = 'Inves Book 600'

    FORMATS = ['epub', 'mobi', 'prc', 'fb2', 'html', 'pdf', 'rtf', 'txt']
    BCD         = [0x110, 0x323]

    VENDOR_NAME = ['INVES_E6', 'INVES-WI', 'POCKETBO']
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = ['00INVES_E600', 'INVES-WIBOOK',
            'OK_POCKET_611_61']


class BOOQ(EB600):
    name = 'Booq Device Interface'
    gui_name = 'bq Reader'

    FORMATS = ['epub', 'mobi', 'prc', 'fb2', 'pdf', 'doc', 'rtf', 'txt', 'html']

    VENDOR_NAME = ['NETRONIX', '36LBOOKS']
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = ['EB600', 'ELEQTOR']


class MENTOR(EB600):

    name = 'Astak Mentor EB600'
    gui_name = 'Mentor'
    description = _('Communicate with the Astak Mentor EB600')
    FORMATS = ['epub', 'fb2', 'mobi', 'prc', 'pdf', 'txt']

    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = 'MENTOR'


class ELONEX(EB600):

    name = 'Elonex 600EB'
    gui_name = 'Elonex'

    FORMATS = ['epub', 'pdf', 'txt', 'html']

    VENDOR_NAME = 'ELONEX'
    WINDOWS_MAIN_MEM = 'EBOOK'
    WINDOWS_CARD_A_MEM = 'EBOOK'

    @classmethod
    def can_handle(cls, dev, debug=False):
        return dev[3] == 'Elonex' and dev[4] == 'eBook'


class POCKETBOOK301(USBMS):

    name           = 'PocketBook 301 Device Interface'
    description    = _('Communicate with the PocketBook 301 Reader.')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']
    FORMATS = ['epub', 'fb2', 'prc', 'mobi', 'pdf', 'djvu', 'rtf', 'chm', 'txt']

    SUPPORTS_SUB_DIRS = True

    MAIN_MEMORY_VOLUME_LABEL  = 'PocketBook 301 Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'PocketBook 301 Storage Card'

    VENDOR_ID   = [0x1]
    PRODUCT_ID  = [0x301]
    BCD         = [0x132]


class POCKETBOOK602(USBMS):

    name = 'PocketBook Pro 602/902 Device Interface'
    description    = _('Communicate with the PocketBook 515/602/603/902/903/Pro 912 reader.')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']
    FORMATS = ['epub', 'fb2', 'prc', 'mobi', 'pdf', 'djvu', 'rtf', 'chm',
            'doc', 'tcr', 'txt']

    EBOOK_DIR_MAIN = 'books'
    SUPPORTS_SUB_DIRS = True
    SCAN_FROM_ROOT = True

    VENDOR_ID   = [0x0525]
    PRODUCT_ID  = [0xa4a5]
    BCD         = [0x0324, 0x0330, 0x0399]

    VENDOR_NAME = ['', 'LINUX']
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = ['PB602', 'PB603', 'PB902',
            'PB903', 'Pocket912', 'PB', 'FILE-STOR_GADGET']


class POCKETBOOK622(POCKETBOOK602):

    name = 'PocketBook 622 Device Interface'
    description    = _('Communicate with the PocketBook 622 and 623 readers.')
    EBOOK_DIR_MAIN = ''

    VENDOR_ID   = [0x0489]
    PRODUCT_ID  = [0xe107, 0xcff1]
    BCD         = [0x0326]

    VENDOR_NAME = 'LINUX'
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = 'FILE-STOR_GADGET'


class POCKETBOOK360P(POCKETBOOK602):

    name = 'PocketBook 360+ Device Interface'
    description    = _('Communicate with the PocketBook 360+ reader.')
    BCD         = [0x0323]
    EBOOK_DIR_MAIN = ''

    VENDOR_NAME = '__POCKET'
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = 'BOOK_USB_STORAGE'


class POCKETBOOK701(USBMS):

    name = 'PocketBook 701 Device Interface'
    description = _('Communicate with the PocketBook 701')
    author = _('Kovid Goyal')

    supported_platforms = ['windows', 'osx', 'linux']
    FORMATS = ['epub', 'fb2', 'prc', 'mobi', 'pdf', 'djvu', 'rtf', 'chm',
            'doc', 'tcr', 'txt']

    EBOOK_DIR_MAIN = 'books'
    SUPPORTS_SUB_DIRS = True

    VENDOR_ID   = [0x18d1]
    PRODUCT_ID  = [0xa004]
    BCD         = [0x0224]

    VENDOR_NAME = 'ANDROID'
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = '__UMS_COMPOSITE'

    def windows_sort_drives(self, drives):
        if len(drives) < 2:
            return drives
        main = drives.get('main', None)
        carda = drives.get('carda', None)
        if main and carda:
            drives['main'] = carda
            drives['carda'] = main
        return drives


class POCKETBOOK740(USBMS):

    name = 'PocketBook 701 Device Interface'
    description = _('Communicate with the PocketBook 740')
    supported_platforms = ['windows', 'osx', 'linux']
    FORMATS = ['epub', 'fb2', 'prc', 'mobi', 'pdf', 'djvu', 'rtf', 'chm',
            'doc', 'tcr', 'txt']
    EBOOK_DIR_MAIN = 'books'
    SUPPORTS_SUB_DIRS = True
    SCAN_FROM_ROOT = True

    VENDOR_ID   = [0x18d1]
    PRODUCT_ID  = [0x0001]
    BCD         = [0x0101]


class PI2(EB600):

    name           = 'Infibeam Pi2 Device Interface'
    gui_name       = 'Infibeam Pi2'
    author         = 'Michael Scalet'
    description    = _('Communicate with the Infibeam Pi2 reader.')
    version        = (1,0,1)

    # Ordered list of supported formats
    FORMATS     = ['epub', 'mobi', 'prc', 'html', 'htm', 'doc', 'pdf', 'rtf',
            'txt']

    VENDOR_NAME      = 'INFIBEAM'
    WINDOWS_MAIN_MEM = 'INFIBEAM_PI'
    WINDOWS_CARD_A_MEM = 'INFIBEAM_PI'

    DELETE_EXTS = ['.rec']
