__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import os
from calibre.ptempfile import PersistentTemporaryFile

try:
    from PIL import ImageFont
    ImageFont
except ImportError:
    import ImageFont

'''
Default fonts used in the PRS500
'''

SYSTEM_FONT_PATH = '/usr/share/fonts/truetype/ttf-liberation/'

FONT_MAP = {
            'Swis721 BT Roman'     : 'tt0003m_',
            'Dutch801 Rm BT Roman' : 'tt0011m_',
            'Courier10 BT Roman'   : 'tt0419m_',
            }

LIBERATION_FONT_MAP = {
            'Swis721 BT Roman'     : 'LiberationSans_Regular',
            'Dutch801 Rm BT Roman' : 'LiberationSerif_Regular',
            'Courier10 BT Roman'   : 'LiberationMono_Regular',
            }

SYSTEM_FONT_MAP = {}
for key, val in LIBERATION_FONT_MAP.items():
    SYSTEM_FONT_MAP[key] = SYSTEM_FONT_PATH + val.replace('_', '-') + '.ttf'

FONT_FILE_MAP = {}

def get_font_path(name):
    if FONT_FILE_MAP.has_key(name) and os.access(FONT_FILE_MAP[name].name, os.R_OK):
        return FONT_FILE_MAP[name].name

    # translate font into file name
    fname = FONT_MAP[name]

    # first, check configuration in /etc/
    etc_file = os.path.join(os.path.sep, 'etc', 'calibre', 'fonts', fname + '.ttf')
    if os.access(etc_file, os.R_OK):
        return etc_file

    # then, try calibre shipped ones
    try:
        try:
            font_mod = __import__('calibre.ebooks.lrf.fonts.prs500', {}, {},
                                  [fname], -1)
            getattr(font_mod, fname)
        except (ImportError, AttributeError):
            font_mod = __import__('calibre.ebooks.lrf.fonts.liberation', {}, {},
                                  [LIBERATION_FONT_MAP[name]], -1)
        p = PersistentTemporaryFile('.ttf', 'font_')
        p.write(getattr(font_mod, fname).font_data)
        p.close()
        FONT_FILE_MAP[name] = p
        return p.name
    except ImportError:
        pass

    # finally, try system default ones
    if SYSTEM_FONT_MAP.has_key(name) and os.access(SYSTEM_FONT_MAP[name], os.R_OK):
        return SYSTEM_FONT_MAP[name]

    # not found
    raise SystemError, 'font %s (in file %s) not installed' % (name, fname)

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
