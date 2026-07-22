# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

"""
Device driver for IRex Iliad
"""

from calibre.devices.usbms.driver import USBMS
from calibre.utils.localization import _


class ILIAD(USBMS):
    name = 'IRex Iliad Device Interface'
    description = _('Communicate with the IRex Iliad e-book reader.')
    author = 'John Schember'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    # Be sure these have an entry in calibre.devices.mime
    FORMATS = ['mobi', 'prc', 'html', 'pdf', 'txt']

    VENDOR_ID = [0x04CC]
    PRODUCT_ID = [0x1A64]
    BCD = [0x100]

    VENDOR_NAME = 'IREX'
    WINDOWS_MAIN_MEM = 'ILIAD'

    # OSX_MAIN_MEM = ''

    MAIN_MEMORY_VOLUME_LABEL = 'IRex Iliad Main Memory'

    EBOOK_DIR_MAIN = 'books'
    DELETE_EXTS = ['.mbp']
    SUPPORTS_SUB_DIRS = True
