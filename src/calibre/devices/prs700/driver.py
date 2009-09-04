# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Device driver for the SONY PRS-700
'''

from calibre.devices.prs505.driver import PRS505
import re

class PRS700(PRS505):

    name           = 'PRS-700 Device Interface'
    description    = _('Communicate with the Sony PRS-700 eBook reader.')
    author         = _('Kovid Goyal and John Schember')
    gui_name       = 'SONY Touch edition'
    supported_platforms = ['windows', 'osx', 'linux']

    BCD          = [0x31a]

    WINDOWS_MAIN_MEM = re.compile('PRS-[67]00')
    WINDOWS_CARD_A_MEM = re.compile(r'PRS-[67]00/\S+:MS')
    WINDOWS_CARD_B_MEM = re.compile(r'PRS-[67]00/\S+:SD')

    OSX_MAIN_MEM   = re.compile(r'Sony PRS-((700/[^:]+)|(600)) Media')
    OSX_CARD_A_MEM = re.compile(r'Sony PRS-((700/[^:]+:)|(600 ))MS Media')
    OSX_CARD_B_MEM = re.compile(r'Sony PRS-((700/[^:]+:)|(600 ))SD Media')


