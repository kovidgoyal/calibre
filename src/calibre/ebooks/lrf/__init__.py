__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
"""
This package contains logic to read and write LRF files.
The LRF file format is documented at U{http://www.sven.de/librie/Librie/LrfFormat}.
"""

from calibre.ebooks.lrf.pylrs.pylrs import Book as _Book
from calibre.ebooks.lrf.pylrs.pylrs import TextBlock, Header, \
                                             TextStyle, BlockStyle
from calibre.ebooks.lrf.fonts import FONT_FILE_MAP
from calibre.ebooks import ConversionError

__docformat__ = "epytext"

class LRFParseError(Exception):
    pass


class PRS500_PROFILE(object):
    screen_width  = 600
    screen_height = 775
    dpi           = 166
    # Number of pixels to subtract from screen_height when calculating height of text area
    fudge         = 0
    font_size     = 10  #: Default (in pt)
    parindent     = 10  #: Default (in pt)
    line_space    = 1.2 #: Default (in pt)
    header_font_size = 6  #: In pt
    header_height    = 30 #: In px
    default_fonts    = { 'sans': "Swis721 BT Roman", 'mono': "Courier10 BT Roman",
                         'serif': "Dutch801 Rm BT Roman"}

    name = 'prs500'

def find_custom_fonts(options, logger):
    from calibre.utils.fonts.scanner import font_scanner
    fonts = {'serif' : None, 'sans' : None, 'mono' : None}
    def family(cmd):
        return cmd.split(',')[-1].strip()
    if options.serif_family:
        f = family(options.serif_family)
        fonts['serif'] = font_scanner.legacy_fonts_for_family(f)
        if not fonts['serif']:
            logger.warn('Unable to find serif family %s'%f)
    if options.sans_family:
        f = family(options.sans_family)
        fonts['sans'] = font_scanner.legacy_fonts_for_family(f)
        if not fonts['sans']:
            logger.warn('Unable to find sans family %s'%f)
    if options.mono_family:
        f = family(options.mono_family)
        fonts['mono'] = font_scanner.legacy_fonts_for_family(f)
        if not fonts['mono']:
            logger.warn('Unable to find mono family %s'%f)
    return fonts


def Book(options, logger, font_delta=0, header=None,
         profile=PRS500_PROFILE, **settings):
    from uuid import uuid4
    ps = {}
    ps['topmargin']      = options.top_margin
    ps['evensidemargin'] = options.left_margin
    ps['oddsidemargin']  = options.left_margin
    ps['textwidth']      = profile.screen_width - (options.left_margin + options.right_margin)
    ps['textheight']     = profile.screen_height - (options.top_margin + options.bottom_margin) \
                                                 - profile.fudge
    if header:
        hdr = Header()
        hb = TextBlock(textStyle=TextStyle(align='foot',
                                           fontsize=int(profile.header_font_size*10)),
                       blockStyle=BlockStyle(blockwidth=ps['textwidth']))
        hb.append(header)
        hdr.PutObj(hb)
        ps['headheight'] = profile.header_height
        ps['headsep']    = options.header_separation
        ps['header']     = hdr
        ps['topmargin']  = 0
        ps['textheight'] = profile.screen_height - (options.bottom_margin + ps['topmargin']) \
                                                 - ps['headheight'] - ps['headsep'] - profile.fudge

    fontsize = int(10*profile.font_size+font_delta*20)
    baselineskip = fontsize + 20
    fonts = find_custom_fonts(options, logger)
    tsd = dict(fontsize=fontsize,
               parindent=int(10*profile.parindent),
               linespace=int(10*profile.line_space),
               baselineskip=baselineskip,
               wordspace=10*options.wordspace)
    if fonts['serif'] and fonts['serif'].has_key('normal'):
        tsd['fontfacename'] = fonts['serif']['normal'][1]

    book = _Book(textstyledefault=tsd,
                pagestyledefault=ps,
                blockstyledefault=dict(blockwidth=ps['textwidth']),
                bookid=uuid4().hex,
                **settings)
    for family in fonts.keys():
        if fonts[family]:
            for font in fonts[family].values():
                book.embed_font(*font)
                FONT_FILE_MAP[font[1]] = font[0]

    for family in ['serif', 'sans', 'mono']:
        if not fonts[family]:
            fonts[family] = { 'normal' : (None, profile.default_fonts[family]) }
        elif not fonts[family].has_key('normal'):
            raise ConversionError, 'Could not find the normal version of the ' + family + ' font'
    return book, fonts

