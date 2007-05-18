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
import pkg_resources
from PIL import ImageFont
'''
Default fonts used in the PRS500
'''
FONT_MAP = {
            'Swis721 BT Roman'     : 'tt0003m_.ttf',
            'Dutch801 Rm BT Roman' : 'tt0011m_.ttf',
            'Courier10 BT Roman'   : 'tt0419m_.ttf'
            }

def get_font(name, size, encoding='unic'):
    '''
    Get an ImageFont object by name. 
    @param size: Size in pts
    @param encoding: Font encoding to use. E.g. 'unic', 'symbol', 'ADOB', 'ADBE', 'aprm'
    '''
    if name in FONT_MAP.keys():
        path = pkg_resources.resource_filename('libprs500.ebooks.lrf.fonts', FONT_MAP[name])
        return ImageFont.truetype(path, size, encoding=encoding)
        