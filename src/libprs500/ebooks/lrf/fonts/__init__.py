##    Copyright (C) 2006 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
from libprs500.ebooks.lrf.fonts.prs500 import tt0419m_
from libprs500.ebooks.lrf.fonts.prs500 import tt0011m_
import sys, os
from libprs500 import iswindows
from libprs500.ptempfile import PersistentTemporaryFile

try:
    from PIL import ImageFont
except ImportError:
    import ImageFont
    
'''
Default fonts used in the PRS500
'''
from libprs500.ebooks.lrf.fonts.prs500 import tt0003m_, tt0011m_, tt0419m_

FONT_MAP = {
            'Swis721 BT Roman'     : tt0003m_,
            'Dutch801 Rm BT Roman' : tt0011m_,
            'Courier10 BT Roman'   : tt0419m_,
            }
FONT_FILE_MAP = {}

def get_font_path(name):
    if FONT_FILE_MAP.has_key(name) and os.access(FONT_FILE_MAP[name].name, os.R_OK):
        return FONT_FILE_MAP[name].name
    p = PersistentTemporaryFile('.ttf', 'font_')
    p.write(FONT_MAP[name].font_data)
    p.close()
    FONT_FILE_MAP[name] = p
    return p.name
    

def get_font(name, size, encoding='unic'):
    '''
    Get an ImageFont object by name. 
    @param size: Font height in pixels. To convert from pts:
                 sz in pixels = (dpi/72) * size in pts
    @param encoding: Font encoding to use. E.g. 'unic', 'symbol', 'ADOB', 'ADBE', 'aprm'
    @param manager: A dict that will store the PersistentTemporary
    '''
    if name in FONT_MAP.keys():
        path = get_font_path(name)
        return ImageFont.truetype(path, size, encoding=encoding)
    elif name in FONT_FILE_MAP.keys():
        return ImageFont.truetype(FONT_FILE_MAP[name], size, encoding=encoding)