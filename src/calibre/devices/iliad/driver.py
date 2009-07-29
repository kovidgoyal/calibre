# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Device driver for IRex Iliad
'''

import os

from calibre.devices.usbms.driver import USBMS

class ILIAD(USBMS):
    name           = 'IRex Iliad Device Interface'
    description    = _('Communicate with the IRex Iliad eBook reader.')
    author         = _('John Schember')
    supported_platforms = ['windows', 'linux']


    # Ordered list of supported formats
    # Be sure these have an entry in calibre.devices.mime
    FORMATS     = ['mobi', 'prc', 'html', 'pdf', 'txt']

    VENDOR_ID   = [0x04cc]
    PRODUCT_ID  = [0x1a64]
    BCD         = [0x100]

    VENDOR_NAME = 'IREX'
    WINDOWS_MAIN_MEM = 'ILIAD'

    #OSX_MAIN_MEM = ''

    MAIN_MEMORY_VOLUME_LABEL  = 'IRex Iliad Main Memory'

    EBOOK_DIR_MAIN = 'books'
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
