# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Device driver for IRex Digiatal Reader
'''

import os

from calibre.devices.usbms.driver import USBMS

class IREXDR1000(USBMS):
    name           = 'IRex Digital Reader 1000 Device Interface'
    description    = _('Communicate with the IRex Digital Reader 1000 eBook reader.')
    author         = _('John Schember')
    supported_platforms = ['windows', 'osx', 'linux']


    # Ordered list of supported formats
    # Be sure these have an entry in calibre.devices.mime
    FORMATS     = ['epub', 'mobi', 'prc', 'html', 'pdf', 'txt']

    VENDOR_ID   = [0x1e6b]
    PRODUCT_ID  = [0x001]
    BCD         = [0x322]

    VENDOR_NAME = 'IREX'
    WINDOWS_MAIN_MEM = 'DR1000'

    OSX_MAIN_MEM = 'iRex DR1000 Media'

    MAIN_MEMORY_VOLUME_LABEL  = 'IRex Digital Reader 1000 Main Memory'

    EBOOK_DIR_MAIN = 'ebooks'
    SUPPORTS_SUB_DIRS = True

    def delete_books(self, paths, end_session=True):
        for i, path in enumerate(paths):
            self.report_progress((i+1) / float(len(paths)), _('Removing books from device...'))
            if os.path.exists(path):
                os.unlink(path)

                filepath, ext = os.path.splitext(path)

                # Delete the ebook auxiliary file
                if os.path.exists(filepath + '.mbp'):
                    os.unlink(filepath + '.mbp')

                try:
                    os.removedirs(os.path.dirname(path))
                except:
                    pass

        self.report_progress(1.0, _('Removing books from device...'))
