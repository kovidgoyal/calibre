__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Device driver for the SONY PRS-700
'''

from calibre.devices.prs505.driver import PRS505

class PRS700(PRS505):
    
    BCD          = 0x31a
    PRODUCT_NAME = 'PRS-700'
    OSX_NAME     = 'Sony PRS-700'
     
