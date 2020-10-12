

__license__   = 'GPL v3'
__copyright__ = '2011,  Ken <ken at szboeye.com>'
__docformat__ = 'restructuredtext en'

'''
Device driver for BOEYE serial readers
'''

from calibre.devices.usbms.driver import USBMS


class BOEYE_BEX(USBMS):
    name		= 'BOEYE BEX reader driver'
    gui_name	= 'BOEYE BEX'
    description	= _('Communicate with BOEYE BEX Serial e-book readers.')
    author		= 'szboeye'
    supported_platforms = ['windows', 'osx', 'linux']

    FORMATS		= ['epub', 'mobi', 'fb2', 'lit', 'prc', 'pdf', 'rtf', 'txt', 'djvu', 'doc', 'chm', 'html', 'zip', 'pdb']

    VENDOR_ID	= [0x0085]
    PRODUCT_ID	= [0x600]

    VENDOR_NAME	 = 'LINUX'
    WINDOWS_MAIN_MEM = 'FILE-STOR_GADGET'
    OSX_MAIN_MEM	 = 'Linux File-Stor Gadget Media'

    MAIN_MEMORY_VOLUME_LABEL  = 'BOEYE BEX Storage Card'

    EBOOK_DIR_MAIN	  = 'Documents'
    SUPPORTS_SUB_DIRS = True


class BOEYE_BDX(USBMS):
    name		= 'BOEYE BDX reader driver'
    gui_name	= 'BOEYE BDX'
    description	= _('Communicate with BOEYE BDX serial e-book readers.')
    author		= 'szboeye'
    supported_platforms = ['windows', 'osx', 'linux']

    FORMATS		= ['epub', 'mobi', 'fb2', 'lit', 'prc', 'pdf', 'rtf', 'txt', 'djvu', 'doc', 'chm', 'html', 'zip', 'pdb']

    VENDOR_ID	= [0x0085]
    PRODUCT_ID	= [0x800]

    VENDOR_NAME	 = 'LINUX'
    WINDOWS_MAIN_MEM   = 'FILE-STOR_GADGET'
    WINDOWS_CARD_A_MEM = 'FILE-STOR_GADGET'

    OSX_MAIN_MEM	 = 'Linux File-Stor Gadget Media'
    OSX_CARD_A_MEM	 = 'Linux File-Stor Gadget Media'

    MAIN_MEMORY_VOLUME_LABEL  = 'BOEYE BDX Internal Memory'
    STORAGE_CARD_VOLUME_LABEL = 'BOEYE BDX Storage Card'

    EBOOK_DIR_MAIN	 = 'Documents'
    EBOOK_DIR_CARD_A = 'Documents'
    SUPPORTS_SUB_DIRS = True
