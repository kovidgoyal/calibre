# License: GPLv3 Copyright: 2008, Kovid Goyal <kovid at kovidgoyal.net>

from PIL import ImageFont

'''
Default fonts used in the PRS500
'''

LIBERATION_FONT_MAP = {
    'Swis721 BT Roman': 'LiberationSans-Regular',
    'Dutch801 Rm BT Roman': 'LiberationSerif-Regular',
    'Courier10 BT Roman': 'LiberationMono-Regular',
}

# Maps full font name to font file path, the name is None if the font has no full name
FONT_FILE_MAP: dict[str | None, str] = {}


def get_font(name: str, size: float, encoding: str = 'unic') -> ImageFont.FreeTypeFont | None:
    """
    Get an ImageFont object by name.
    @param size: Font height in pixels. To convert from pts:
                 sz in pixels = (dpi/72) * size in pts
    @param encoding: Font encoding to use. E.g. 'unic', 'symbol', 'ADOB', 'ADBE', 'aprm'
    @param manager: A dict that will store the PersistentTemporary
    """
    from calibre.utils.resources import get_path as P

    if name in LIBERATION_FONT_MAP:
        return ImageFont.truetype(P(f'fonts/liberation/{LIBERATION_FONT_MAP[name]}.ttf'), size, encoding=encoding)
    elif name in FONT_FILE_MAP:
        return ImageFont.truetype(FONT_FILE_MAP[name], size, encoding=encoding)
