__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com>'
'''
Device driver for Bookeen's Cybook Gen 3
'''

import os, shutil
from itertools import cycle

from calibre.devices.errors import FreeSpaceError
from calibre.devices.usbms.driver import USBMS
import calibre.devices.cybookg3.t2b as t2b
from calibre.devices.errors import FreeSpaceError

class CYBOOKG3(USBMS):
    # Ordered list of supported formats
    # Be sure these have an entry in calibre.devices.mime
    FORMATS     = ['mobi', 'prc', 'html', 'pdf', 'rtf', 'txt']
    
    VENDOR_ID   = [0x0bda, 0x3034]
    PRODUCT_ID  = [0x0703, 0x1795]
    BCD         = [0x110, 0x132]
    
    VENDOR_NAME = 'BOOKEEN'
    WINDOWS_MAIN_MEM = 'CYBOOK_GEN3__-FD'
    WINDOWS_CARD_MEM = 'CYBOOK_GEN3__-SD'
    
    OSX_MAIN_MEM = 'Bookeen Cybook Gen3 -FD Media'
    OSX_CARD_MEM = 'Bookeen Cybook Gen3 -SD Media'
    
    MAIN_MEMORY_VOLUME_LABEL  = 'Cybook Gen 3 Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'Cybook Gen 3 Storage Card'
    
    EBOOK_DIR_MAIN = "eBooks"
    EBOOK_DIR_CARD = "eBooks"
    SUPPORTS_SUB_DIRS = True
    
    THUMBNAIL_HEIGHT = 144
    
    def upload_books(self, files, names, on_card=False, end_session=True, 
                     metadata=None):
        if on_card and not self._card_prefix:
            raise ValueError(_('The reader has no storage card connected.'))
            
        if not on_card:
            path = os.path.join(self._main_prefix, self.EBOOK_DIR_MAIN)
        else:
            path = os.path.join(self._card_prefix, self.EBOOK_DIR_CARD)

        def get_size(obj):
            if hasattr(obj, 'seek'):
                obj.seek(0, os.SEEK_END)
                size = obj.tell()
                obj.seek(0)
                return size
            return os.path.getsize(obj)

        sizes = [get_size(f) for f in files]
        size = sum(sizes)

        if on_card and size > self.free_space()[2] - 1024*1024:
            raise FreeSpaceError(_("There is insufficient free space on the storage card"))
        if not on_card and size > self.free_space()[0] - 2*1024*1024: 
            raise FreeSpaceError(_("There is insufficient free space in main memory"))

        paths = []
        names = iter(names)
        metadata = iter(metadata)
        
        for infile in files:
            newpath = path
            mdata = metadata.next()
            
            if self.SUPPORTS_SUB_DIRS:
                if 'tags' in mdata.keys():
                    for tag in mdata['tags']:
                        if tag.startswith('/'):
                            newpath += tag
                            newpath = os.path.normpath(newpath)
                            break

            if not os.path.exists(newpath):
                os.makedirs(newpath)
            
            filepath = os.path.join(newpath, names.next())                
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
    
        return zip(paths, cycle([on_card]))

    def delete_books(self, paths, end_session=True):
        for path in paths:
            if os.path.exists(path):
                os.unlink(path)
                
                filepath, ext = os.path.splitext(path)
                
                # Delete the ebook auxiliary file
                if os.path.exists(filepath + '.mbp'):
                    os.unlink(filepath + '.mbp')
                
                # Delete the thumbnails file auto generated for the ebook
                if os.path.exists(filepath + '_6090.t2b'):
                    os.unlink(filepath + '_6090.t2b')
                    
                try:
                    os.removedirs(os.path.dirname(path))
                except:
                    pass

