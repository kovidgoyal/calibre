__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com>'
'''
Device driver for Amazon's Kindle
'''

import os, fnmatch

from calibre.devices.usbms.driver import USBMS
from calibre.devices.usbms.cli import CLI

class KINDLE(USBMS, CLI):
    MIME_MAP   = { 
                'azw' : 'application/azw',
                'mobi' : 'application/mobi',
                'prc' : 'application/prc',
                'txt' : 'text/plain',
              }
    # Ordered list of supported formats
    FORMATS     = MIME_MAP.keys()
    
    VENDOR_ID   = 0x1949
    PRODUCT_ID  = 0x0001
    BCD         = 0x399
    
    VENDOR_NAME = 'AMAZON'
    PRODUCT_NAME = 'KINDLE'
    
    MAIN_MEMORY_VOLUME_LABEL  = 'Kindle Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'Kindle Storage Card'
    
    EBOOK_DIR = "documents"

