# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Device driver for Amazon's Kindle
'''

import os
import re
import sys

from calibre.devices.usbms.driver import USBMS

class KINDLE(USBMS):

    name           = 'Kindle Device Interface'
    gui_name       = 'Amazon Kindle'
    description    = _('Communicate with the Kindle eBook reader.')
    author         = 'John Schember'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['azw', 'mobi', 'prc', 'azw1', 'tpz', 'txt']

    VENDOR_ID   = [0x1949]
    PRODUCT_ID  = [0x0001]
    BCD         = [0x399]

    VENDOR_NAME = 'KINDLE'
    WINDOWS_MAIN_MEM = 'INTERNAL_STORAGE'
    WINDOWS_CARD_A_MEM = 'CARD_STORAGE'

    OSX_MAIN_MEM = 'Kindle Internal Storage Media'
    OSX_CARD_A_MEM = 'Kindle Card Storage Media'

    MAIN_MEMORY_VOLUME_LABEL  = 'Kindle Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'Kindle Storage Card'

    EBOOK_DIR_MAIN = 'documents'
    EBOOK_DIR_CARD_A = 'documents'
    DELETE_EXTS = ['.mbp']
    SUPPORTS_SUB_DIRS = True

    WIRELESS_FILE_NAME_PATTERN = re.compile(
    r'(?P<title>[^-]+)-asin_(?P<asin>[a-zA-Z\d]{10,})-type_(?P<type>\w{4})-v_(?P<index>\d+).*')

    @classmethod
    def metadata_from_path(cls, path):
        mi = cls.metadata_from_formats([path])
        if mi.title == _('Unknown') or ('-asin' in mi.title and '-type' in mi.title):
            match = cls.WIRELESS_FILE_NAME_PATTERN.match(os.path.basename(path))
            if match is not None:
                mi.title = match.group('title')
                if not isinstance(mi.title, unicode):
                    mi.title = mi.title.decode(sys.getfilesystemencoding(),
                                               'replace')
        return mi


class KINDLE2(KINDLE):

    name           = 'Kindle 2 Device Interface'
    description    = _('Communicate with the Kindle 2 eBook reader.')

    FORMATS        = KINDLE.FORMATS + ['pdf']
    PRODUCT_ID = [0x0002]
    BCD        = [0x0100]


class KINDLE_DX(KINDLE2):

    name           = 'Kindle DX Device Interface'
    description    = _('Communicate with the Kindle DX eBook reader.')


    PRODUCT_ID = [0x0003]
    BCD        = [0x0100]
