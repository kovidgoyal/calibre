# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Device driver for the SONY PRS-700
'''

from calibre.devices.prs505.driver import PRS505

class PRS700(PRS505):

    name           = 'PRS-700 Device Interface'
    description    = _('Communicate with the Sony PRS-700 eBook reader.')
    author         = _('Kovid Goyal and John Schember')
    supported_platforms = ['windows', 'osx', 'linux']

    BCD          = [0x31a]

    WINDOWS_MAIN_MEM = 'PRS-700'
    WINDOWS_CARD_A_MEM = 'PRS-700/UC:MS'
    WINDOWS_CARD_B_MEM = 'PRS-700/UC:SD'

    OSX_MAIN_MEM = 'Sony PRS-700/UC Media'
    OSX_CARD_A_MEM = 'Sony PRS-700/UC:MS Media'
    OSX_CARD_B_MEM = 'Sony PRS-700/UC:SD'
