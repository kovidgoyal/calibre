__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.devices.usbms.driver import USBMS

class TECLAST_K3(USBMS):

    name           = 'Teclast K3/K5 Device Interface'
    gui_name       = 'K3/K5'
    description    = _('Communicate with the Teclast K3/K5 reader.')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'fb2', 'doc', 'pdf', 'txt']

    VENDOR_ID   = [0x071b]
    PRODUCT_ID  = [0x3203]
    BCD         = [0x0000, 0x0100]

    VENDOR_NAME      = ['TECLAST', 'IMAGIN']
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = ['DIGITAL_PLAYER', 'TL-K5',
            'EREADER']

    MAIN_MEMORY_VOLUME_LABEL  = 'K3 Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'K3 Storage Card'

    EBOOK_DIR_MAIN = ''
    EBOOK_DIR_CARD_A = ''
    SUPPORTS_SUB_DIRS = True


class NEWSMY(TECLAST_K3):
    name = 'Newsmy device interface'
    gui_name = 'Newsmy'
    description    = _('Communicate with the Newsmy reader.')

    FORMATS = ['epub', 'fb2', 'pdb', 'html', 'pdf', 'txt', 'skt']

    VENDOR_NAME      = ''
    WINDOWS_MAIN_MEM = 'NEWSMY'
    WINDOWS_CARD_A_MEM = 'USBDISK____SD'

class ARCHOS7O(TECLAST_K3):
    name = 'Archos 7O device interface'
    gui_name = 'Archos'
    description    = _('Communicate with the Archos reader.')

    FORMATS = ['epub', 'mobi', 'fb2', 'rtf', 'ap', 'html', 'pdf', 'txt']

    VENDOR_NAME      = 'ARCHOS'
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = 'USB-MSC'

class PICO(NEWSMY):
    name = 'Pico device interface'
    gui_name = 'Pico'
    description    = _('Communicate with the Pico reader.')

    VENDOR_NAME      = ['TECLAST', 'IMAGIN', 'LASER-', '']
    WINDOWS_MAIN_MEM = ['USBDISK__USER', 'EB720']
    EBOOK_DIR_MAIN = 'Books'
    FORMATS = ['EPUB', 'FB2', 'TXT', 'LRC', 'PDB', 'PDF', 'HTML', 'WTXT']
    SCAN_FROM_ROOT = True

class IPAPYRUS(TECLAST_K3):

    name = 'iPapyrus device interface'
    gui_name = 'iPapyrus'
    description    = _('Communicate with the iPapyrus reader.')

    FORMATS = ['epub', 'pdf', 'txt']

    VENDOR_NAME      = ['E_READER', 'EBOOKREA']
    WINDOWS_MAIN_MEM = ''

class SOVOS(TECLAST_K3):

    name = 'Sovos device interface'
    gui_name = 'Sovos'
    description    = _('Communicate with the Sovos reader.')

    FORMATS = ['epub', 'fb2', 'pdf', 'txt']

    VENDOR_NAME      = 'RK28XX'
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = 'USB-MSC'

class SUNSTECH_EB700(TECLAST_K3):
    name = 'Sunstech EB700 device interface'
    gui_name = 'EB700'
    description    = _('Communicate with the Sunstech EB700 reader.')

    FORMATS = ['epub', 'fb2', 'pdf', 'pdb', 'txt']

    VENDOR_NAME = 'SUNEB700'
    WINDOWS_MAIN_MEM = 'USB-MSC'

class STASH(TECLAST_K3):

    name = 'Stash device interface'
    gui_name = 'Stash'
    description    = _('Communicate with the Stash W950 reader.')

    FORMATS = ['epub', 'fb2', 'lrc', 'pdb', 'html', 'fb2', 'wtxt',
            'txt', 'pdf']

    VENDOR_NAME = 'STASH'
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = 'W950'

class WEXLER(TECLAST_K3):

    name = 'Wexler device interface'
    gui_name = 'Wexler'
    description    = _('Communicate with the Wexler reader.')

    FORMATS = ['epub', 'fb2', 'pdf', 'txt']

    VENDOR_NAME = 'WEXLER'
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = 'T7001'

