from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.devices.usbms.driver import USBMS

class BLACKBERRY(USBMS):
    # Ordered list of supported formats
    FORMATS     = ['mobi', 'prc']
    
    VENDOR_ID   = [0x0fca]
    PRODUCT_ID  = [0x8004]
    BCD         = [0x0200]
    
    VENDOR_NAME = 'RIM'
    WINDOWS_MAIN_MEM = 'BLACKBERRY_SD'
    #WINDOWS_CARD_MEM = 'CARD_STORAGE'
    
    #OSX_MAIN_MEM = 'Kindle Internal Storage Media'
    #OSX_CARD_MEM = 'Kindle Card Storage Media'
    
    MAIN_MEMORY_VOLUME_LABEL  = 'Blackberry Main Memory'
    #STORAGE_CARD_VOLUME_LABEL = 'Kindle Storage Card'
    
    EBOOK_DIR_MAIN = 'ebooks'
    #EBOOK_DIR_CARD = "documents"
    SUPPORTS_SUB_DIRS = False

