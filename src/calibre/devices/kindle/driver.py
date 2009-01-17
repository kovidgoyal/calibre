__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com>'
'''
Device driver for Amazon's Kindle
'''

import os, fnmatch

from calibre.devices.usbms.driver import USBMS

class KINDLE(USBMS):
    # Ordered list of supported formats
    FORMATS     = ['azw', 'mobi', 'prc', 'txt']
    
    VENDOR_ID   = 0x1949
    PRODUCT_ID  = 0x0001
    BCD         = [0x399]
    
    VENDOR_NAME = 'KINDLE'
    WINDOWS_MAIN_MEM = 'INTERNAL_STORAGE'
    WINDOWS_CARD_MEM = 'CARD_STORAGE'
    
    OSX_MAIN_MEM = 'Kindle Internal Storage Media'
    OSX_CARD_MEM = 'Kindle Card Storage Media'
    
    MAIN_MEMORY_VOLUME_LABEL  = 'Kindle Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'Kindle Storage Card'
    
    EBOOK_DIR_MAIN = "documents"
    SUPPORTS_SUB_DIRS = True

    def delete_books(self, paths, end_session=True):
        for path in paths:
            if os.path.exists(path):
                os.unlink(path)
                
                filepath, ext = os.path.splitext(path)
                basepath, filename = os.path.split(filepath)
                
                # Delete the ebook auxiliary file
                if os.path.exists(filepath + '.mbp'):
                    os.unlink(filepath + '.mbp')

