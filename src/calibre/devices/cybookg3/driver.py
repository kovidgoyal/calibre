__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com>'
'''
Device driver for Bookeen's Cybook Gen 3
'''

import os, shutil
from itertools import cycle

from calibre.devices.errors import DeviceError, FreeSpaceError
from calibre.devices.usbms.driver import USBMS
import calibre.devices.cybookg3.t2b as t2b

class CYBOOKG3(USBMS):
    name           = 'Cybook Gen 3 Device Interface'
    description    = _('Communicate with the Cybook eBook reader.')
    author         = _('John Schember')
    supported_platforms = ['windows', 'osx', 'linux']


    # Ordered list of supported formats
    # Be sure these have an entry in calibre.devices.mime
    FORMATS     = ['mobi', 'prc', 'html', 'pdf', 'rtf', 'txt']

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

    EBOOK_DIR_MAIN = "eBooks"
    EBOOK_DIR_CARD_A = "eBooks"
    THUMBNAIL_HEIGHT = 144
    SUPPORTS_SUB_DIRS = True

    def upload_books(self, files, names, on_card=None, end_session=True,
                     metadata=None):
        path = self._sanity_check(on_card, files)

        paths = []
        names = iter(names)
        metadata = iter(metadata)

        for i, infile in enumerate(files):
            newpath = path
            mdata = metadata.next()

            if 'tags' in mdata.keys():
                for tag in mdata['tags']:
                    if tag.startswith(_('News')):
                        newpath = os.path.join(newpath, 'news')
                        newpath = os.path.join(newpath, mdata.get('title', ''))
                        newpath = os.path.join(newpath, mdata.get('timestamp', ''))
                    elif tag.startswith('/'):
                        newpath += tag
                        newpath = os.path.normpath(newpath)
                        break

            if newpath == path:
                newpath = os.path.join(newpath, mdata.get('authors', _('Unknown')))
                newpath = os.path.join(newpath, mdata.get('title', _('Unknown')))

            newpath = self._sanitize_path(newpath)
            if not os.path.exists(newpath):
                os.makedirs(newpath)

            filepath = self._sanitize_path(os.path.join(newpath, names.next()))
            paths.append(filepath)

            if hasattr(infile, 'read'):
                infile.seek(0)

                dest = open(filepath, 'wb')
                shutil.copyfileobj(infile, dest, 10*1024*1024)

                dest.flush()
                dest.close()
            else:
                shutil.copy2(infile, filepath)

            coverdata = None
            if 'cover' in mdata.keys():
                if mdata['cover'] != None:
                    coverdata = mdata['cover'][2]

            t2bfile = open('%s_6090.t2b' % (os.path.splitext(filepath)[0]), 'wb')
            t2b.write_t2b(t2bfile, coverdata)
            t2bfile.close()

            self.report_progress(i / float(len(files)), _('Transferring books to device...'))

        self.report_progress(1.0, _('Transferring books to device...'))
        
        return zip(paths, cycle([on_card]))

    def delete_books(self, paths, end_session=True):
        for i, path in enumerate(paths):
            self.report_progress((i+1) / float(len(paths)), _('Removing books from device...'))
            if os.path.exists(path):
                os.unlink(path)

                filepath, ext = os.path.splitext(path)

                # Delete the ebook auxiliary file
                if os.path.exists(filepath + '.mbp'):
                    os.unlink(filepath + '.mbp')
                if os.path.exists(filepath + '.dat'):
                    os.unlink(filepath + '.dat')

                # Delete the thumbnails file auto generated for the ebook
                if os.path.exists(filepath + '_6090.t2b'):
                    os.unlink(filepath + '_6090.t2b')

                try:
                    os.removedirs(os.path.dirname(path))
                except:
                    pass
        self.report_progress(1.0, _('Removing books from device...'))
