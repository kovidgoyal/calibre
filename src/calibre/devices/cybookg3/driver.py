__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com>'
'''
Device driver for Bookeen's Cybook Gen 3
'''

import os, fnmatch

from calibre.devices.usbms.driver import USBMS

class CYBOOKG3(USBMS):
    MIME_MAP   = { 
                'mobi' : 'application/mobi',
                'prc' : 'application/prc',
                'html' : 'application/html', 
                'pdf' : 'application/pdf',  
                'rtf' : 'application/rtf', 
                'txt' : 'text/plain',
              }
    # Ordered list of supported formats
    FORMATS     = MIME_MAP.keys()
    
    VENDOR_ID   = 0x0bda
    PRODUCT_ID  = 0x0703
    BCD         = 0x110
    
    VENDOR_NAME = 'BOOKEEN'
    PRODUCT_NAME = 'CYBOOK_GEN3'
    
    MAIN_MEMORY_VOLUME_LABEL  = 'Cybook Gen 3 Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'Cybook Gen 3 Storage Card'
    
    EBOOK_DIR = "eBooks"

    def delete_books(self, paths, end_session=True):
        for path in paths:
            if os.path.exists(path):
                os.unlink(path)
                
                filepath, ext = os.path.splitext(path)
                basepath, filename = os.path.split(filepath)
                
                # Delete the ebook auxiliary file
                if os.path.exists(filepath + '.mbp'):
                    os.unlink(filepath + '.mbp')
                
                # Delete the thumbnails file auto generated for the ebook
                for p, d, files in os.walk(basepath):
                    for filen in fnmatch.filter(files, filename + "*.t2b"):
                        os.unlink(os.path.join(p, filen))

