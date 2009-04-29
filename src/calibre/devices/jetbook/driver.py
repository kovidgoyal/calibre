__license__   = 'GPL v3'
__copyright__ = '2009, James Ralston <jralston at mindspring.com>'
'''
Device driver for Ectaco Jetbook firmware >= JL04_v030e
'''

import os, shutil
from itertools import cycle

from calibre.devices.errors import FreeSpaceError
from calibre.devices.usbms.driver import USBMS
from calibre.devices.usbms.books import BookList
from calibre import sanitize_file_name as sanitize

class JETBOOK(USBMS):
    # Ordered list of supported formats
    # Be sure these have an entry in calibre.devices.mime
    FORMATS     = [ 'epub', 'mobi', 'prc', 'txt', 'rtf', 'pdf']

    VENDOR_ID   = [0x0525]
    PRODUCT_ID  = [0xa4a5]
    BCD         = [0x314]

    VENDOR_NAME = 'NETCHIP'

    WINDOWS_MAIN_MEM = None
    WINDOWS_CARD_MEM = None

    OSX_MAIN_MEM = None
    OSX_CARD_MEM = None

    MAIN_MEMORY_VOLUME_LABEL  = 'Jetbook Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'Jetbook Storage Card'

    EBOOK_DIR_MAIN = "Books"
    EBOOK_DIR_CARD = "Books"
    SUPPORTS_SUB_DIRS = True

    def upload_books(self, files, names, on_card=False, end_session=True,
                    metadata=None):

        path = self._sanity_check(on_card, files)

        paths = []
        names = iter(names)
        metadata = iter(metadata)

        for infile in files:
            newpath = path

            if self.SUPPORTS_SUB_DIRS:
                mdata = metadata.next()

                if 'tags' in mdata.keys():
                    for tag in mdata['tags']:
                        if tag.startswith('/'):
                            newpath += tag
                            newpath = os.path.normpath(newpath)
                            break

            if not os.path.exists(newpath):
                os.makedirs(newpath)

            author = sanitize(mdata.get('authors','Unknown'))
            title = sanitize(mdata.get('title', 'Unknown'))
            (basename, fileext) = os.path.splitext(os.path.basename(names.next()))
            fname = '%s#%s%s' % (author, title, fileext)

            filepath = os.path.join(newpath, fname)
            paths.append(filepath)

            if hasattr(infile, 'read'):
                infile.seek(0)

                dest = open(filepath, 'wb')
                shutil.copyfileobj(infile, dest, 10*1024*1024)

                dest.flush()
                dest.close()
            else:
                shutil.copy2(infile, filepath)

        return zip(paths, cycle([on_card]))

