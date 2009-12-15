# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Device driver for Bookeen's Cybook Gen 3
'''

import os
from itertools import cycle

from calibre import islinux
from calibre.devices.usbms.driver import USBMS
import calibre.devices.cybookg3.t2b as t2b

class CYBOOKG3(USBMS):

    name           = 'Cybook Gen 3 Device Interface'
    gui_name       = 'Cybook Gen 3'
    description    = _('Communicate with the Cybook Gen 3 eBook reader.')
    author         = 'John Schember'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    # Be sure these have an entry in calibre.devices.mime
    FORMATS     = ['epub', 'mobi', 'prc', 'html', 'pdf', 'rtf', 'txt']

    VENDOR_ID   = [0x0bda, 0x3034]
    PRODUCT_ID  = [0x0703, 0x1795]
    BCD         = [0x110, 0x132]

    VENDOR_NAME = 'BOOKEEN'
    WINDOWS_MAIN_MEM = 'CYBOOK_GEN3__-FD'
    WINDOWS_CARD_A_MEM = 'CYBOOK_GEN3__-SD'

    OSX_MAIN_MEM = 'Bookeen Cybook Gen3 -FD Media'
    OSX_CARD_A_MEM = 'Bookeen Cybook Gen3 -SD Media'

    MAIN_MEMORY_VOLUME_LABEL  = 'Cybook Gen 3 Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'Cybook Gen 3 Storage Card'

    EBOOK_DIR_MAIN = 'eBooks'
    EBOOK_DIR_CARD_A = 'eBooks'
    THUMBNAIL_HEIGHT = 144
    DELETE_EXTS = ['.mbp', '.dat', '_6090.t2b']
    SUPPORTS_SUB_DIRS = True

    def upload_books(self, files, names, on_card=None, end_session=True,
                     metadata=None):

        path = self._sanity_check(on_card, files)

        paths = []
        names = iter(names)
        metadata = iter(metadata)

        for i, infile in enumerate(files):
            mdata, fname = metadata.next(), names.next()
            filepath = self.create_upload_path(path, mdata, fname)
            paths.append(filepath)

            self.put_file(infile, filepath, replace_file=True)

            coverdata = None
            cover = mdata.get('cover', None)
            if cover:
                coverdata = cover[2]

            t2bfile = open('%s_6090.t2b' % (os.path.splitext(filepath)[0]), 'wb')
            t2b.write_t2b(t2bfile, coverdata)
            t2bfile.close()

            self.report_progress(i / float(len(files)), _('Transferring books to device...'))

        self.report_progress(1.0, _('Transferring books to device...'))

        return zip(paths, cycle([on_card]))

    @classmethod
    def can_handle(cls, device_info, debug=False):
        USBMS.can_handle(device_info, debug)
        if islinux:
            return device_info[3] == 'Bookeen' and device_info[4] == 'Cybook Gen3'
        return True


class CYBOOK_OPUS(CYBOOKG3):

    name           = 'Cybook Opus Device Interface'
    gui_name       = 'Cybook Opus'
    description    = _('Communicate with the Cybook Opus eBook reader.')
    author         = 'John Schember'
    supported_platforms = ['windows', 'osx', 'linux']

    FORMATS = ['epub', 'pdf', 'txt']

    VENDOR_ID   = [0x0bda]
    PRODUCT_ID  = [0x0703]
    BCD         = [0x110]

    VENDOR_NAME = 'BOOKEEN'
    WINDOWS_MAIN_MEM = 'CYBOOK_OPUS__-FD'
    WINDOWS_CARD_A_MEM = 'CYBOOK_OPUS__-SD'

    OSX_MAIN_MEM = 'Bookeen Cybook Opus -FD Media'
    OSX_CARD_A_MEM = 'Bookeen Cybook Opus -SD Media'

    EBOOK_DIR_MAIN = 'eBooks'
    EBOOK_DIR_CARD_A = 'eBooks'
    SUPPORTS_SUB_DIRS = True

    @classmethod
    def can_handle(cls, device_info, debug=False):
        USBMS.can_handle(device_info, debug)
        if islinux:
            return device_info[3] == 'Bookeen'
        return True
