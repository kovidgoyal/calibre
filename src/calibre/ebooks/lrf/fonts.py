__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

from PIL import ImageFont

'''
Default fonts used in the PRS500
'''


LIBERATION_FONT_MAP = {
            'Swis721 BT Roman'     : 'LiberationSans-Regular',
            'Dutch801 Rm BT Roman' : 'LiberationSerif-Regular',
            'Courier10 BT Roman'   : 'LiberationMono-Regular',
            }

FONT_FILE_MAP = {}


def get_font(name, size, encoding='unic'):
    '''
    Get an ImageFont object by name.
    @param size: Font height in pixels. To convert from pts:
                 sz in pixels = (dpi/72) * size in pts
    @param encoding: Font encoding to use. E.g. 'unic', 'symbol', 'ADOB', 'ADBE', 'aprm'
    @param manager: A dict that will store the PersistentTemporary
    '''
    if name in LIBERATION_FONT_MAP:
        return ImageFont.truetype(P('fonts/liberation/%s.ttf' % LIBERATION_FONT_MAP[name]), size, encoding=encoding)
    elif name in FONT_FILE_MAP:
        return ImageFont.truetype(FONT_FILE_MAP[name], size, encoding=encoding)
